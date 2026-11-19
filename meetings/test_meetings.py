import datetime
from io import BytesIO

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework.test import APIClient

from meetings import services
from meetings.models import ActionItem, Meeting
from task.models import Notification, Task

MEETINGS = '/api/meetings/meetings/'
ITEMS = '/api/meetings/action-items/'
DAY = datetime.date(2001, 3, 1)            # old dates: nothing real can clash with them


class MeetingBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        def user(name, **extra):
            return User.objects.create_user(name, f'{name}@example.com', 'x', first_name=name.title(), **extra)
        cls.creator = user('mmcreator')
        cls.attendee = user('mmattendee')
        cls.owner = user('mmowner')                  # gets action items, does not attend
        cls.stranger = user('mmstranger')
        cls.staff = user('mmstaff', is_staff=True)

    def setUp(self):
        self.api = APIClient()
        self.as_user(self.creator)

    def as_user(self, user):
        self.api.force_authenticate(user)

    def payload(self, **extra):
        data = {
            'title': 'Weekly production review', 'meeting_type': 'Production', 'meeting_date': DAY.isoformat(),
            'meeting_time': '11:00', 'location': 'Factory conference room',
            'agenda': '1. Pending jobs', 'minutes': 'Printing-2 runs only jobs with cylinders ready.',
            'attendees': [{'user': self.attendee.pk}, {'name': 'Rahul', 'organisation': 'Sahara Agro'}],
            'action_items': [
                {'description': 'Confirm film delivery', 'owner': self.owner.pk, 'due_date': '2001-03-05',
                 'priority': 'HIGH'},
                {'description': 'Check cylinders', 'owner': self.creator.pk, 'due_date': '2001-03-03'},
            ],
        }
        data.update(extra)
        return data

    def create(self, **extra):
        response = self.api.post(MEETINGS, self.payload(**extra), format='json')
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def final(self, **extra):
        meeting = self.create(**extra)
        response = self.api.post(f'{MEETINGS}{meeting["id"]}/finalise/')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def detail(self, meeting_id):
        return self.api.get(f'{MEETINGS}{meeting_id}/')


class CreateAndNumberingTests(MeetingBase):
    def test_create_with_attendees_and_action_items(self):
        meeting = self.create()
        self.assertEqual(meeting['status'], 'draft')
        self.assertEqual(meeting['created_by'], self.creator.pk)
        self.assertRegex(meeting['number'], r'^MOM-2001-\d{3}$')
        self.assertEqual([a['name'] for a in meeting['attendees']], ['Mmattendee', 'Rahul'])
        self.assertEqual([a['is_external'] for a in meeting['attendees']], [False, True])
        self.assertEqual([i['description'] for i in meeting['action_items']], ['Confirm film delivery', 'Check cylinders'])
        self.assertEqual((meeting['total_items'], meeting['open_items']), (2, 2))

    def test_a_draft_makes_no_tasks_yet(self):
        self.create()
        self.assertEqual(Task.objects.filter(taskname__startswith='MOM-2001-').count(), 0)

    def test_numbers_count_up_within_a_year_and_restart_each_year(self):
        a, b = self.create(), self.create()
        c = self.create(meeting_date='2002-01-10')
        self.assertEqual(int(b['number'][-3:]), int(a['number'][-3:]) + 1)
        self.assertEqual(c['number'], 'MOM-2002-001')

    def test_a_deleted_number_is_not_reused_below_the_highest(self):
        first, second = self.create(), self.create()
        Meeting.objects.filter(pk=first['id']).delete()
        third = self.create()
        self.assertGreater(int(third['number'][-3:]), int(second['number'][-3:]))

    def test_an_attendee_user_gets_their_name_filled_in(self):
        meeting = self.create(attendees=[{'user': self.attendee.pk}])
        self.assertEqual(meeting['attendees'][0]['name'], 'Mmattendee')

    def test_validation(self):
        bad = lambda **extra: self.api.post(MEETINGS, self.payload(**extra), format='json')
        self.assertEqual(bad(title='   ').status_code, 400)
        self.assertEqual(bad(attendees=[{}]).status_code, 400)                          # neither user nor name
        self.assertEqual(bad(attendees=[{'user': self.attendee.pk}, {'user': self.attendee.pk}]).status_code, 400)
        self.assertEqual(bad(action_items=[{'description': 'x', 'due_date': '2001-03-05'}]).status_code, 400)  # no owner
        self.assertEqual(bad(action_items=[{'description': '  ', 'owner': self.owner.pk,
                                            'due_date': '2001-03-05'}]).status_code, 400)
        self.assertEqual(bad(meeting_type='Picnic').status_code, 400)
        self.assertEqual(Meeting.objects.filter(title='Weekly production review').count(), 0)   # nothing half-saved

    def test_status_and_number_cannot_be_set_by_the_client(self):
        meeting = self.create(status='final', number='MOM-1999-999')
        self.assertEqual(meeting['status'], 'draft')
        self.assertNotEqual(meeting['number'], 'MOM-1999-999')

    def test_anonymous_is_refused(self):
        self.api.force_authenticate(None)
        self.assertIn(self.api.get(MEETINGS).status_code, (401, 403))


class VisibilityAndPermissionTests(MeetingBase):
    def setUp(self):
        super().setUp()
        self.meeting = self.create()

    def ids(self, user):
        self.as_user(user)
        return {m['id'] for m in self.api.get(MEETINGS, {'page_size': 200}).json()['results']}

    def test_who_can_see_it(self):
        self.assertIn(self.meeting['id'], self.ids(self.creator))
        self.assertIn(self.meeting['id'], self.ids(self.attendee))
        self.assertIn(self.meeting['id'], self.ids(self.owner))                  # was given an action item
        self.assertIn(self.meeting['id'], self.ids(self.staff))
        self.assertNotIn(self.meeting['id'], self.ids(self.stranger))

    def test_a_stranger_gets_a_404_not_the_minutes(self):
        self.as_user(self.stranger)
        self.assertEqual(self.detail(self.meeting['id']).status_code, 404)
        self.assertEqual(self.api.get(f'{MEETINGS}{self.meeting["id"]}/pdf/').status_code, 404)

    def test_only_the_creator_or_staff_can_edit(self):
        url = f'{MEETINGS}{self.meeting["id"]}/'
        self.as_user(self.attendee)
        self.assertEqual(self.api.patch(url, {'minutes': 'hacked'}, format='json').status_code, 404)
        self.as_user(self.creator)
        self.assertEqual(self.api.patch(url, {'minutes': 'by creator'}, format='json').status_code, 200)
        self.as_user(self.staff)
        self.assertEqual(self.api.patch(url, {'minutes': 'by staff'}, format='json').status_code, 200)
        self.assertEqual(Meeting.objects.get(pk=self.meeting['id']).minutes, '<div>by staff</div>')

    def test_can_edit_is_reported_to_the_page(self):
        self.assertTrue(self.detail(self.meeting['id']).json()['can_edit'])
        self.as_user(self.attendee)
        self.assertFalse(self.detail(self.meeting['id']).json()['can_edit'])
        self.as_user(self.staff)
        self.assertTrue(self.detail(self.meeting['id']).json()['can_edit'])

    def test_deleting(self):
        url = f'{MEETINGS}{self.meeting["id"]}/'
        self.as_user(self.attendee)
        self.assertEqual(self.api.delete(url).status_code, 404)
        self.as_user(self.creator)
        self.assertEqual(self.api.delete(url).status_code, 204)             # a draft: its creator may

    def test_a_finalised_meeting_can_only_be_deleted_by_staff(self):
        meeting = self.final()
        url = f'{MEETINGS}{meeting["id"]}/'
        self.assertEqual(self.api.delete(url).status_code, 404)
        self.as_user(self.staff)
        self.assertEqual(self.api.delete(url).status_code, 204)
        self.assertEqual(Task.objects.filter(taskname__startswith=meeting['number']).count(), 2)  # the tasks stay


class FinaliseTests(MeetingBase):
    def test_finalising_makes_a_task_for_each_action_item(self):
        meeting = self.final()
        self.assertEqual(meeting['status'], 'final')
        self.assertEqual(meeting['finalised_by_name'], 'Mmcreator')
        tasks = Task.objects.filter(taskname__startswith=meeting['number'])
        self.assertEqual(tasks.count(), 2)
        film = tasks.get(task_alloted_to=self.owner)
        self.assertEqual(film.taskname, f'{meeting["number"]}: Confirm film delivery')
        self.assertEqual(film.priority, 'HIGH')
        self.assertEqual(film.target_date, datetime.datetime(2001, 3, 5, 18, 0))
        self.assertEqual(film.createdby, self.creator)
        self.assertIn('Weekly production review', film.description)
        self.assertEqual(ActionItem.objects.get(task=film).description, 'Confirm film delivery')

    def test_the_owner_is_notified_but_not_the_creator_of_their_own_item(self):
        meeting = self.final()
        self.assertEqual(Notification.objects.filter(user=self.owner, task__taskname__startswith=meeting['number']).count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.creator, task__taskname__startswith=meeting['number']).count(), 0)

    def test_finalising_needs_minutes(self):
        meeting = self.create(minutes='   ')
        response = self.api.post(f'{MEETINGS}{meeting["id"]}/finalise/')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Meeting.objects.get(pk=meeting['id']).status, 'draft')

    def test_it_cannot_be_finalised_twice(self):
        meeting = self.final()
        self.assertEqual(self.api.post(f'{MEETINGS}{meeting["id"]}/finalise/').status_code, 400)
        self.assertEqual(Task.objects.filter(taskname__startswith=meeting['number']).count(), 2)

    def test_only_the_creator_or_staff_can_finalise(self):
        meeting = self.create()
        self.as_user(self.attendee)
        self.assertEqual(self.api.post(f'{MEETINGS}{meeting["id"]}/finalise/').status_code, 404)
        self.as_user(self.staff)
        self.assertEqual(self.api.post(f'{MEETINGS}{meeting["id"]}/finalise/').status_code, 200)


class EditingAFinalMeetingTests(MeetingBase):
    def setUp(self):
        super().setUp()
        self.meeting = self.final()
        self.url = f'{MEETINGS}{self.meeting["id"]}/'

    def items(self):
        return self.detail(self.meeting['id']).json()['action_items']

    def test_a_new_item_gets_its_task_straight_away(self):
        rows = [{'id': i['id'], 'description': i['description'], 'owner': i['owner'], 'due_date': i['due_date'],
                 'priority': i['priority']} for i in self.items()]
        rows.append({'description': 'Extra follow-up', 'owner': self.owner.pk, 'due_date': '2001-03-09'})
        self.assertEqual(self.api.patch(self.url, {'action_items': rows}, format='json').status_code, 200)
        self.assertTrue(Task.objects.filter(taskname=f'{self.meeting["number"]}: Extra follow-up').exists())

    def test_editing_an_item_updates_its_task(self):
        item = [i for i in self.items() if i['owner'] == self.owner.pk][0]
        rows = [{'id': item['id'], 'description': 'Confirm film delivery by Friday', 'owner': self.attendee.pk,
                 'due_date': '2001-03-08', 'priority': 'LOW'}]
        keep_other = [i for i in self.items() if i['id'] != item['id']]
        rows += [{'id': i['id'], 'description': i['description'], 'owner': i['owner'], 'due_date': i['due_date'],
                  'priority': i['priority']} for i in keep_other]
        self.assertEqual(self.api.patch(self.url, {'action_items': rows}, format='json').status_code, 200)
        task = Task.objects.get(pk=item['task'])
        self.assertEqual(task.taskname, f'{self.meeting["number"]}: Confirm film delivery by Friday')
        self.assertEqual((task.task_alloted_to, task.priority), (self.attendee, 'LOW'))
        self.assertEqual(task.target_date.date(), datetime.date(2001, 3, 8))
        self.assertTrue(Notification.objects.filter(user=self.attendee, task=task).exists())   # new owner told

    def test_an_item_with_a_task_cannot_be_removed(self):
        keep = [{'id': i['id'], 'description': i['description'], 'owner': i['owner'], 'due_date': i['due_date']}
                for i in self.items()][:1]
        response = self.api.patch(self.url, {'action_items': keep}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(len(self.items()), 2)

    def test_a_closed_task_is_left_alone_when_the_item_changes(self):
        item = self.items()[0]
        Task.objects.filter(pk=item['task']).update(is_closed=True)
        before = Task.objects.get(pk=item['task']).taskname
        rows = [{'id': i['id'], 'description': 'Renamed' if i['id'] == item['id'] else i['description'],
                 'owner': i['owner'], 'due_date': i['due_date']} for i in self.items()]
        self.api.patch(self.url, {'action_items': rows}, format='json')
        self.assertEqual(Task.objects.get(pk=item['task']).taskname, before)

    def test_an_unknown_item_id_is_refused(self):
        rows = [{'id': 999999999, 'description': 'x', 'owner': self.owner.pk, 'due_date': '2001-03-05'}]
        self.assertEqual(self.api.patch(self.url, {'action_items': rows}, format='json').status_code, 400)


class EditingADraftTests(MeetingBase):
    def test_draft_items_can_be_added_changed_and_removed_freely(self):
        meeting = self.create()
        url = f'{MEETINGS}{meeting["id"]}/'
        first = meeting['action_items'][0]
        rows = [{'id': first['id'], 'description': 'Changed', 'owner': self.owner.pk, 'due_date': '2001-03-06'},
                {'description': 'Brand new', 'owner': self.creator.pk, 'due_date': '2001-03-07'}]
        response = self.api.patch(url, {'action_items': rows}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([i['description'] for i in response.json()['action_items']], ['Changed', 'Brand new'])
        self.assertEqual(Task.objects.filter(taskname__contains='Brand new').count(), 0)        # still no tasks

    def test_attendees_are_replaced_and_left_alone_when_not_sent(self):
        meeting = self.create()
        url = f'{MEETINGS}{meeting["id"]}/'
        self.api.patch(url, {'title': 'Retitled'}, format='json')
        self.assertEqual(len(self.detail(meeting['id']).json()['attendees']), 2)
        self.api.patch(url, {'attendees': [{'name': 'Only one'}]}, format='json')
        self.assertEqual([a['name'] for a in self.detail(meeting['id']).json()['attendees']], ['Only one'])


class ActionItemStatusTests(MeetingBase):
    def setUp(self):
        super().setUp()
        self.meeting = self.final()
        self.item = [i for i in self.meeting['action_items'] if i['owner'] == self.owner.pk][0]
        self.url = f'{ITEMS}{self.item["id"]}/'

    def test_the_owner_can_mark_it_done_and_that_closes_the_task(self):
        self.as_user(self.owner)
        response = self.api.post(f'{self.url}mark-done/')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['status'], 'done')
        task = Task.objects.get(pk=self.item['task'])
        self.assertTrue(task.is_closed)
        self.assertIsNotNone(task.close_date)

    def test_the_creator_can_mark_it_done_and_the_owner_is_told(self):
        before = Notification.objects.filter(user=self.owner).count()
        self.assertEqual(self.api.post(f'{self.url}mark-done/').status_code, 200)
        self.assertEqual(Notification.objects.filter(user=self.owner).count(), before + 1)

    def test_a_stranger_cannot(self):
        self.as_user(self.stranger)
        self.assertEqual(self.api.post(f'{self.url}mark-done/').status_code, 404)

    def test_an_attendee_who_is_neither_owner_nor_creator_cannot(self):
        self.as_user(self.attendee)
        self.assertEqual(self.api.post(f'{self.url}mark-done/').status_code, 404)    # PermissionDenied shows as 404

    def test_reopening(self):
        self.as_user(self.owner)
        self.api.post(f'{self.url}mark-done/')
        response = self.api.post(f'{self.url}reopen/')
        self.assertEqual(response.json()['status'], 'open')
        task = Task.objects.get(pk=self.item['task'])
        self.assertFalse(task.is_closed)
        self.assertIsNone(task.close_date)

    def test_closing_the_task_in_tasks_shows_the_item_as_done(self):
        Task.objects.filter(pk=self.item['task']).update(is_closed=True)
        detail = self.detail(self.meeting['id']).json()
        done = [i['status'] for i in detail['action_items'] if i['id'] == self.item['id']]
        self.assertEqual(done, ['done'])
        self.assertEqual(detail['open_items'], 1)

    def test_marking_done_twice_is_harmless(self):
        self.api.post(f'{self.url}mark-done/')
        self.assertEqual(self.api.post(f'{self.url}mark-done/').status_code, 200)


class MyActionItemsTests(MeetingBase):
    def setUp(self):
        super().setUp()
        past = (timezone.now().date() - datetime.timedelta(days=3)).isoformat()
        soon = (timezone.now().date() + datetime.timedelta(days=3)).isoformat()
        self.final(action_items=[
            {'description': 'Overdue one', 'owner': self.owner.pk, 'due_date': past},
            {'description': 'Soon one', 'owner': self.owner.pk, 'due_date': soon},
            {'description': 'Creators own', 'owner': self.creator.pk, 'due_date': soon},
        ])
        self.as_user(self.owner)

    def names(self, **params):
        return [i['description'] for i in self.api.get(ITEMS, {**params, 'page_size': 100}).json()['results']]

    def test_owner_me(self):
        self.assertEqual(self.names(owner='me'), ['Overdue one', 'Soon one'])

    def test_a_non_attending_owner_still_sees_their_items(self):
        self.assertEqual(len(self.names()), 3)                      # the meeting is visible to them as an action owner

    def test_overdue_and_status_filters(self):
        self.assertEqual(self.names(owner='me', overdue='true'), ['Overdue one'])
        item = self.api.get(ITEMS, {'owner': 'me'}).json()['results'][0]
        self.api.post(f'{ITEMS}{item["id"]}/mark-done/')
        self.assertEqual(self.names(owner='me', status='open'), ['Soon one'])
        self.assertEqual(self.names(owner='me', status='done'), ['Overdue one'])
        self.assertEqual(self.names(owner='me', overdue='true'), [])        # done is no longer overdue

    def test_is_overdue_flag(self):
        rows = {i['description']: i['is_overdue'] for i in self.api.get(ITEMS, {'page_size': 100}).json()['results']}
        self.assertEqual((rows['Overdue one'], rows['Soon one']), (True, False))

    def test_summary(self):
        self.assertEqual(self.api.get(f'{ITEMS}summary/').json(), {'open': 2, 'overdue': 1})

    def test_a_stranger_sees_none_of_it(self):
        self.as_user(self.stranger)
        self.assertEqual(self.names(), [])


class PreviousOpenItemsTests(MeetingBase):
    def test_open_items_of_earlier_final_meetings_of_the_same_type_show_up(self):
        earlier = self.final(meeting_date='2001-02-01')
        new = self.create(meeting_date='2001-03-01', action_items=[])
        shown = self.detail(new['id']).json()['previous_open_items']
        self.assertEqual({i['meeting_number'] for i in shown}, {earlier['number']})
        self.assertEqual(len(shown), 2)

    def test_done_items_other_types_later_meetings_and_drafts_do_not(self):
        earlier = self.final(meeting_date='2001-02-01')
        Task.objects.filter(taskname__startswith=earlier['number']).update(is_closed=True)       # all done
        self.final(meeting_date='2001-02-02', meeting_type='Customer')                          # another type
        self.create(meeting_date='2001-02-03')                                                    # a draft
        new = self.create(meeting_date='2001-03-01', action_items=[])
        self.assertEqual(self.detail(new['id']).json()['previous_open_items'], [])
        later = self.final(meeting_date='2001-04-01')
        self.assertTrue(later)
        self.assertEqual(self.detail(new['id']).json()['previous_open_items'], [])               # later is not "previous"


class ListFilterTests(MeetingBase):
    def setUp(self):
        super().setUp()
        self.a = self.create(title='Printing review', meeting_date='2001-03-01')
        self.b = self.final(title='Customer visit', meeting_type='Customer', meeting_date='2001-04-01',
                            attendees=[{'name': 'Mr Patil', 'organisation': 'Patil Foods'}], action_items=[])

    def titles(self, **params):
        rows = self.api.get(MEETINGS, {**params, 'page_size': 100}).json()['results']
        return {m['title'] for m in rows if m['title'] in ('Printing review', 'Customer visit')}

    def test_search_covers_title_minutes_and_attendee_names(self):
        self.assertEqual(self.titles(search='Printing review'), {'Printing review'})
        self.assertEqual(self.titles(search='Patil'), {'Customer visit'})
        self.assertEqual(self.titles(search='cylinders ready'), {'Printing review', 'Customer visit'})

    def test_type_status_and_dates(self):
        self.assertEqual(self.titles(meeting_type='Customer'), {'Customer visit'})
        self.assertEqual(self.titles(status='draft'), {'Printing review'})
        self.assertEqual(self.titles(date_from='2001-03-15', date_to='2001-12-31'), {'Customer visit'})
        self.assertEqual(self.titles(date_to='2001-03-01'), {'Printing review'})

    def test_attendee_and_mine(self):
        self.assertEqual(self.titles(attendee=self.attendee.pk), {'Printing review'})
        self.as_user(self.attendee)
        self.assertEqual(self.titles(mine='true'), {'Printing review'})

    def test_has_open_items(self):
        self.assertEqual(self.titles(has_open_items='true'), {'Printing review'})
        self.assertEqual(self.titles(has_open_items='false'), {'Customer visit'})

    def test_the_list_rows_carry_counts(self):
        rows = {m['title']: m for m in self.api.get(MEETINGS, {'page_size': 100}).json()['results']}
        review = rows['Printing review']
        self.assertEqual((review['attendee_count'], review['external_count']), (2, 1))
        self.assertEqual((review['total_items'], review['open_items']), (2, 2))
        self.assertEqual(rows['Customer visit']['total_items'], 0)
        self.assertEqual(review['created_by_name'], 'Mmcreator')

    def test_a_stranger_sees_neither(self):
        self.as_user(self.stranger)
        self.assertEqual(self.titles(), set())


class ListOrderingTests(MeetingBase):
    def test_the_list_is_newest_first_and_pages_do_not_overlap(self):
        for day in (3, 1, 5, 2, 4):
            self.create(title=f'Order {day}', meeting_date=f'2001-03-0{day}')
        titles = lambda **q: [m['title'] for m in self.api.get(MEETINGS, {'search': 'Order', **q}).json()['results']]
        self.assertEqual(titles(), [f'Order {d}' for d in (5, 4, 3, 2, 1)])
        self.assertEqual(titles(page_size=2, page=1) + titles(page_size=2, page=2) + titles(page_size=2, page=3),
                         [f'Order {d}' for d in (5, 4, 3, 2, 1)])

    def test_same_day_meetings_keep_a_stable_order_newest_created_first(self):
        first = self.create(title='Same day A')['id']
        second = self.create(title='Same day B')['id']
        ids = [m['id'] for m in self.api.get(MEETINGS, {'search': 'Same day'}).json()['results']]
        self.assertEqual(ids, [second, first])

    def test_the_list_query_is_ordered(self):
        from meetings.api_viewsets import MeetingViewSet
        view = MeetingViewSet()
        view.action = 'list'
        view.request = type('R', (), {'user': self.staff})()
        self.assertTrue(view.get_queryset().ordered)


class PdfAndExcelTests(MeetingBase):
    def test_the_minutes_pdf(self):
        meeting = self.final(title='Review: "Printing" & lamination <urgent>')
        response = self.api.get(f'{MEETINGS}{meeting["id"]}/pdf/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn('inline', response['Content-Disposition'])
        self.assertIn(meeting['number'], response['Content-Disposition'])

    def test_a_draft_and_odd_text_still_make_a_pdf(self):
        meeting = self.create(minutes='Line one\n\nLine three with symbols ₹ ✓ & < > "quotes"',
                              agenda='', attendees=[], action_items=[])
        self.assertTrue(self.api.get(f'{MEETINGS}{meeting["id"]}/pdf/').content.startswith(b'%PDF'))

    def test_the_list_as_excel(self):
        self.final(title='Excel meeting')
        response = self.api.get(f'{MEETINGS}excel/', {'search': 'Excel meeting'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('spreadsheetml', response['Content-Type'])
        self.assertIn('attachment', response['Content-Disposition'])
        sheet = load_workbook(BytesIO(response.content)).active
        rows = list(sheet.iter_rows(min_row=4, values_only=True))
        self.assertEqual(rows[0][:3], ('No.', 'Meeting', 'Type'))
        self.assertEqual(len(rows), 2)                                        # header + the one matching meeting
        data = dict(zip(rows[0], rows[1]))
        self.assertEqual((data['Meeting'], data['Status'], data['Attendees'], data['Outside']),
                         ('Excel meeting', 'Final', 2, 1))
        self.assertEqual((data['Action items'], data['Open items']), (2, 2))
        self.assertEqual(data['Date'], datetime.datetime(2001, 3, 1))

    def test_excel_only_contains_what_the_user_may_see(self):
        self.create(title='Secret one')
        self.as_user(self.stranger)
        response = self.api.get(f'{MEETINGS}excel/')
        rows = list(load_workbook(BytesIO(response.content)).active.iter_rows(min_row=5, values_only=True))
        self.assertFalse(any(row[1] == 'Secret one' for row in rows))


class RichTextTests(MeetingBase):
    def save(self, **extra):
        meeting = self.create(**extra)
        return self.detail(meeting['id']).json()

    def test_formatting_is_kept(self):
        html = '<div>Agreed: <b>ship Friday</b> and <i>call</i> <u>them</u></div><ul><li>one</li><li>two</li></ul>'
        meeting = self.save(minutes=html)
        self.assertEqual(meeting['minutes'], html)

    def test_scripts_handlers_styles_and_unsafe_links_are_removed(self):
        meeting = self.save(minutes=(
            '<div onclick="steal()" style="color:red">Hello</div>'
            '<script>alert(1)</script><style>p{display:none}</style>'
            '<img src=x onerror="alert(2)">'
            '<a href="javascript:alert(3)">bad</a> <a href="  JaVa	ScRiPt:alert(4)">bad2</a>'
            '<a href="https://example.com/a?b=1&c=2" onclick="x()">good</a>'
            '<iframe src="https://evil.example"></iframe>'))
        html = meeting['minutes']
        for danger in ('script', 'alert', 'onclick', 'onerror', 'style', 'javascript', 'iframe', '<img'):
            self.assertNotIn(danger.lower(), html.lower(), danger)
        self.assertIn('<div>Hello</div>', html)
        self.assertIn('href="https://example.com/a?b=1&amp;c=2"', html)
        self.assertIn('rel="noopener noreferrer"', html)

    def test_font_size_is_kept_but_other_font_settings_are_not(self):
        meeting = self.save(minutes='<div><font size="5" color="red" face="Comic" style="x:y">Big</font> '
                                    '<font size="99">odd</font></div>')
        self.assertEqual(meeting['minutes'], '<div><font size="5">Big</font> <font>odd</font></div>')

    def test_sized_text_with_no_other_tag_is_still_html(self):
        # what the editor sends for a single line: bare text with only a size tag in it
        meeting = self.save(minutes='Small and <font size="6">BIG</font> words')
        self.assertEqual(meeting['minutes'], 'Small and <font size="6">BIG</font> words')

    def test_the_pdf_makes_sized_text_bigger(self):
        from meetings.pdfs import build_minutes_pdf
        meeting = self.create(minutes='<div>normal <font size="7">HUGE</font> <font size="1">tiny</font></div>')
        self.assertTrue(build_minutes_pdf(Meeting.objects.get(pk=meeting['id'])).startswith(b'%PDF'))

    def test_broken_markup_is_closed(self):
        self.assertEqual(self.save(minutes='<div><b>open and never closed')['minutes'], '<div><b>open and never closed</b></div>')

    def test_text_typed_as_html_stays_text(self):
        meeting = self.save(minutes='<div>1 &lt; 2 &amp; &lt;script&gt;x&lt;/script&gt;</div>')
        self.assertEqual(meeting['minutes'], '<div>1 &lt; 2 &amp; &lt;script&gt;x&lt;/script&gt;</div>')

    def test_plain_text_from_before_the_editor_shows_with_its_line_breaks(self):
        meeting = self.save(minutes='Line one\n\nLine & three <not a tag>', agenda='')
        self.assertEqual(meeting['minutes'],
                         '<div>Line one</div><div><br></div><div>Line &amp; three &lt;not a tag&gt;</div>')
        # saved before the editor existed: the database holds raw text, the API still returns safe html
        Meeting.objects.filter(pk=meeting['id']).update(minutes='Old <minutes>\nsecond')
        self.assertEqual(self.detail(meeting['id']).json()['minutes'], '<div>Old &lt;minutes&gt;</div><div>second</div>')

    def test_an_empty_editor_counts_as_nothing_written(self):
        meeting = self.save(minutes='<div><br></div><p>&nbsp;</p>', agenda='<div> </div>')
        self.assertEqual((meeting['minutes'], meeting['agenda']), ('', ''))
        response = self.api.post(f'{MEETINGS}{meeting["id"]}/finalise/')
        self.assertEqual(response.status_code, 400)
        self.assertIn('minutes', response.content.decode().lower())

    def test_search_finds_words_not_tags(self):
        self.create(title='Tagged', minutes='<div>Discuss <b>laminator</b> repair</div>')
        self.create(title='Other', minutes='<div>nothing here</div>')
        titles = lambda q: {m['title'] for m in self.api.get(MEETINGS, {'search': q}).json()['results']}
        self.assertEqual(titles('laminator'), {'Tagged'})
        self.assertEqual(titles('div'), set())
        self.assertEqual(titles('strong'), set())

    def test_the_pdf_draws_lists_bold_and_headings(self):
        from meetings.pdfs import build_minutes_pdf
        meeting = self.create(
            agenda='<ol><li>First</li><li>Second<ul><li>nested</li></ul></li></ol>',
            minutes='<h3>Decisions</h3><div>We <b>agreed <i>fully</i></b> on <a href="https://example.com">this</a></div>'
                    '<blockquote>quoted</blockquote><pre>code line</pre><div>a<br>b</div>')
        pdf = build_minutes_pdf(Meeting.objects.get(pk=meeting['id']))
        self.assertTrue(pdf.startswith(b'%PDF'))
        try:
            import fitz
        except ImportError:
            return
        text = ''.join(page.get_text() for page in fitz.open(stream=pdf, filetype='pdf'))
        for word in ('Decisions', 'agreed', 'fully', 'nested', 'quoted', 'code line'):
            self.assertIn(word, text)
        for tag in ('<b>', '<li>', '<div>'):
            self.assertNotIn(tag, text)


class ModulePayloadTests(MeetingBase):
    def test_every_logged_in_user_gets_the_module(self):
        self.as_user(self.stranger)
        self.assertTrue(self.api.get('/api/crm/me/').json()['modules']['meetings'])


class ServiceTests(MeetingBase):
    def test_finalise_is_all_or_nothing(self):
        meeting = Meeting.objects.get(pk=self.create()['id'])
        original = services.create_task_for

        def boom(item, actor):
            raise RuntimeError('task creation failed')
        services.create_task_for = boom
        try:
            with self.assertRaises(RuntimeError):
                services.finalise(meeting, self.creator)
        finally:
            services.create_task_for = original
        meeting.refresh_from_db()
        self.assertEqual(meeting.status, 'draft')
