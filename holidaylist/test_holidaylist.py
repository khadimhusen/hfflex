import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from attendance import services as attendance
from attendance.models import AttendanceDay
from employee.models import Worker
from holidaylist.models import Holiday

URL = '/api/holidays/holidays/'
DAY = datetime.date(2001, 3, 2)               # old dates: nothing real can clash with them


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('hlstaff', 'a@example.com', 'x', is_staff=True)
        cls.plain = User.objects.create_user('hlplain', 'b@example.com', 'x')

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.staff)

    def add(self, name='Holi', date=DAY, **extra):
        response = self.api.post(URL, {'date': date.isoformat(), 'name': name, 'kind': 'Festival', **extra},
                                 format='json')
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()


class ListAndEditTests(Base):
    def test_anyone_logged_in_reads_the_list(self):
        self.add()
        self.api.force_authenticate(self.plain)
        response = self.api.get(URL, {'year': 2001})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([h['name'] for h in response.json()['results']], ['Holi'])

    def test_only_staff_change_it(self):
        holiday = self.add()
        self.api.force_authenticate(self.plain)
        body = {'date': '2001-04-01', 'name': 'Sneaky', 'kind': 'Other'}
        self.assertIn(self.api.post(URL, body, format='json').status_code, (403, 404))
        self.assertIn(self.api.patch(f'{URL}{holiday["id"]}/', {'name': 'x'}, format='json').status_code, (403, 404))
        self.assertIn(self.api.delete(f'{URL}{holiday["id"]}/').status_code, (403, 404))
        self.assertEqual(Holiday.objects.get(pk=holiday['id']).name, 'Holi')
        self.api.force_authenticate(None)
        self.assertIn(self.api.get(URL).status_code, (401, 403, 404))

    def test_a_holiday_shows_its_weekday_and_kind(self):
        row = self.add('Day off', datetime.date(2001, 3, 2), kind='Company')
        self.assertEqual((row['weekday'], row['kind_display']), ('Friday', 'Company'))

    def test_filter_by_year_and_kind_and_search_and_order(self):
        self.add('B day', datetime.date(2001, 5, 1), kind='National')
        self.add('A day', datetime.date(2001, 3, 1))
        self.add('Next year', datetime.date(2002, 1, 26), kind='National')
        names = lambda **q: [h['name'] for h in self.api.get(URL, q).json()['results']]
        self.assertEqual(names(year=2001), ['A day', 'B day'])                    # oldest first
        self.assertEqual(names(year=2001, kind='National'), ['B day'])
        self.assertEqual(names(search='next'), ['Next year'])

    def test_two_holidays_cannot_share_a_date(self):
        self.add('Holi')
        response = self.api.post(URL, {'date': DAY.isoformat(), 'name': 'Other', 'kind': 'Other'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('already on the list: Holi', response.content.decode())

    def test_a_holiday_can_be_edited_without_clashing_with_itself(self):
        holiday = self.add('Holi')
        response = self.api.patch(f'{URL}{holiday["id"]}/', {'name': 'Holi (Dhulivandan)', 'notes': ' x '}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual((response.json()['name'], response.json()['notes']), ('Holi (Dhulivandan)', 'x'))

    def test_a_name_is_needed(self):
        response = self.api.post(URL, {'date': DAY.isoformat(), 'name': '   ', 'kind': 'Other'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_upcoming_starts_today_and_skips_the_past(self):
        today = datetime.date.today()
        self.add('Long ago', DAY)
        self.add('Today', today)
        self.add('Soon', today + datetime.timedelta(days=3))
        self.add('Later', today + datetime.timedelta(days=9))
        rows = self.api.get(URL + 'upcoming/', {'count': 2}).json()
        self.assertEqual([(r['name'], r['days_away']) for r in rows], [('Today', 0), ('Soon', 3)])


class AttendanceFollowsTheListTests(Base):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        joined = datetime.date(2000, 1, 1)
        cls.free = Worker.objects.create(worker_name='HL FREE', emp_code='8801', date_of_join=joined)
        cls.on_leave = Worker.objects.create(worker_name='HL LEAVE', emp_code='8802', date_of_join=joined)
        cls.auto_absent = Worker.objects.create(worker_name='HL ABSENT', emp_code='8803', date_of_join=joined)
        cls.later = Worker.objects.create(worker_name='HL LATER', emp_code='8804',
                                          date_of_join=datetime.date(2005, 1, 1))     # not yet employed
        cls.left = Worker.objects.create(worker_name='HL LEFT', emp_code='8805', date_of_join=joined,
                                         date_of_releave=datetime.date(2001, 1, 1))

    def row(self, worker, day=DAY):
        return AttendanceDay.objects.filter(worker=worker, date=day).first()

    def test_every_employed_worker_gets_a_holiday_row(self):
        self.add('Holi')
        row = self.row(self.free)
        self.assertEqual((row.status, row.remarks, row.is_manual), (AttendanceDay.HOLIDAY, 'Holiday: Holi', False))
        self.assertIsNone(self.row(self.later))                  # not employed yet
        self.assertIsNone(self.row(self.left))                   # already left

    def test_a_decision_made_by_hand_is_kept(self):
        attendance.set_day(self.on_leave, DAY, AttendanceDay.LEAVE, None, remarks='wedding')
        self.add('Holi')
        row = self.row(self.on_leave)
        self.assertEqual((row.status, row.remarks, row.is_manual), (AttendanceDay.LEAVE, 'wedding', True))

    def test_the_systems_own_absent_rows_become_holiday(self):
        AttendanceDay.objects.create(worker=self.auto_absent, date=DAY, status=AttendanceDay.ABSENT, remarks='No punch')
        self.add('Holi')
        self.assertEqual(self.row(self.auto_absent).status, AttendanceDay.HOLIDAY)

    def test_someone_who_works_the_holiday_is_present(self):
        self.add('Holi')
        attendance.record_punches([
            {'emp_code': '8801', 'punched_at': datetime.datetime.combine(DAY, datetime.time(8, 0))},
            {'emp_code': '8801', 'punched_at': datetime.datetime.combine(DAY, datetime.time(17, 30))},
        ])
        self.assertEqual(self.row(self.free).status, AttendanceDay.PRESENT)

    def test_renaming_updates_the_rows(self):
        holiday = self.add('Holi')
        self.api.patch(f'{URL}{holiday["id"]}/', {'name': 'Dhulivandan'}, format='json')
        self.assertEqual(self.row(self.free).remarks, 'Holiday: Dhulivandan')

    def test_moving_a_holiday_moves_the_rows(self):
        holiday = self.add('Holi')
        moved = DAY + datetime.timedelta(days=1)
        self.api.patch(f'{URL}{holiday["id"]}/', {'date': moved.isoformat()}, format='json')
        self.assertEqual(self.row(self.free, moved).status, AttendanceDay.HOLIDAY)
        self.assertEqual(self.row(self.free, DAY).status, AttendanceDay.ABSENT)       # a past day with no punch again

    def test_deleting_a_past_holiday_puts_absent_back(self):
        holiday = self.add('Holi')
        self.api.delete(f'{URL}{holiday["id"]}/')
        self.assertEqual(self.row(self.free).status, AttendanceDay.ABSENT)

    def test_deleting_a_future_holiday_just_removes_the_rows(self):
        future = datetime.date.today() + datetime.timedelta(days=30)
        holiday = self.add('Soon', future)
        self.assertEqual(self.row(self.free, future).status, AttendanceDay.HOLIDAY)
        self.api.delete(f'{URL}{holiday["id"]}/')
        self.assertIsNone(self.row(self.free, future))

    def test_deleting_leaves_hand_made_holiday_rows_alone(self):
        attendance.set_day(self.free, DAY, AttendanceDay.HOLIDAY, None, remarks='set by hand')
        holiday = self.add('Holi')
        self.api.delete(f'{URL}{holiday["id"]}/')
        row = self.row(self.free)
        self.assertEqual((row.status, row.remarks, row.is_manual), (AttendanceDay.HOLIDAY, 'set by hand', True))

    def test_mark_remaining_absent_uses_holiday_on_a_holiday(self):
        Holiday.objects.create(date=DAY, name='Holi')            # made without the screens: no rows yet
        attendance.mark_absent(DAY, self.staff)
        row = self.row(self.free)
        self.assertEqual((row.status, row.remarks), (AttendanceDay.HOLIDAY, 'Holiday: Holi'))

    def test_mark_remaining_absent_is_still_absent_on_a_normal_day(self):
        attendance.mark_absent(DAY, self.staff)
        self.assertEqual(self.row(self.free).status, AttendanceDay.ABSENT)
