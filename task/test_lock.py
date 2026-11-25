"""Overdue tasks lock the assignee until the creator gives them a new target date."""
import datetime
from unittest import mock

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from task import lock, popup
from task.models import Notification, Task, TaskMsg
from task.test_review import FakeSession

TODAY = datetime.date.today()
LOCKED_URL = '/task/locked/'


def when(days_ago, hour=12):
    return datetime.datetime.combine(TODAY - datetime.timedelta(days=days_ago), datetime.time(hour, 0))


class LockBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.boss = User.objects.create_user('lockboss', 'a@example.com', 'x', first_name='Bossy')
        cls.worker = User.objects.create_user('lockworker', 'b@example.com', 'x')
        cls.other = User.objects.create_user('lockother', 'c@example.com', 'x')

    def setUp(self):
        patcher = mock.patch('task.lock.CACHE_SECONDS', 0)                  # most tests want no caching
        patcher.start()
        self.addCleanup(patcher.stop)

    def make(self, priority='HIGH', overdue=0, who=None, by=None, **extra):
        return Task.objects.create(taskname=f'LOCKTEST {priority} {overdue}', description='x', priority=priority,
                                   target_date=when(overdue), task_alloted_to=who or self.worker,
                                   createdby=by if by is not None else self.boss, **extra)

    def client_for(self, user):
        client = Client()
        client.force_login(user)
        return client


class LimitTests(LockBase):
    def test_the_limits_for_each_priority(self):
        self.assertEqual((lock.limit_for('HIGH'), lock.limit_for('NORMAL'), lock.limit_for('LOW')), (2, 3, 6))

    def test_exactly_at_the_limit_is_still_allowed_one_day_more_locks(self):
        for priority, limit in (('HIGH', 2), ('NORMAL', 3), ('LOW', 6)):
            allowed = self.make(priority, overdue=limit)
            locking = self.make(priority, overdue=limit + 1)
            self.assertFalse(lock.is_locking(allowed), f'{priority} {limit} days')
            self.assertTrue(lock.is_locking(locking), f'{priority} {limit + 1} days')

    def test_the_database_query_agrees_with_the_rule(self):
        tasks = [self.make(p, overdue=d) for p in ('HIGH', 'NORMAL', 'LOW') for d in range(0, 9)]
        from_query = set(lock.locked_tasks(self.worker).values_list('pk', flat=True))
        from_rule = {t.pk for t in tasks if lock.is_locking(t)}
        self.assertEqual(from_query, from_rule)
        self.assertTrue(from_rule and from_rule != {t.pk for t in tasks})

    def test_a_task_not_overdue_at_all_never_locks(self):
        for days in (0, -1, -30):
            self.assertFalse(lock.is_locking(self.make('HIGH', overdue=days)))

    def test_an_unknown_priority_counts_as_low(self):
        self.assertFalse(lock.is_locking(self.make('URGENT', overdue=6)))
        self.assertTrue(lock.is_locking(self.make('URGENT', overdue=7)))
        self.assertIn(self.make('', overdue=9).pk, set(lock.locked_tasks(self.worker).values_list('pk', flat=True)))

    def test_what_does_not_lock(self):
        closed = self.make(overdue=10, is_closed=True)
        asked_to_close = self.make(overdue=10, request_to_close=True)
        nobody_allotted = Task.objects.create(taskname='LOCKTEST orphan', description='x', priority='HIGH',
                                              target_date=when(10), task_alloted_to=self.worker, createdby=None)
        for task in (closed, asked_to_close, nobody_allotted):
            self.assertFalse(lock.is_locking(task), task.taskname)
        ids = set(lock.locked_tasks(self.worker).values_list('pk', flat=True))
        self.assertFalse(ids & {closed.pk, asked_to_close.pk, nobody_allotted.pk})

    def test_a_task_the_user_allotted_to_themselves_locks_them_just_the_same(self):
        for priority, limit in (('HIGH', 2), ('NORMAL', 3), ('LOW', 6)):
            within = self.make(priority, overdue=limit, who=self.boss, by=self.boss)
            past = self.make(priority, overdue=limit + 1, who=self.boss, by=self.boss)
            self.assertFalse(lock.is_locking(within), priority)
            self.assertTrue(lock.is_locking(past), priority)
        ids = set(lock.locked_tasks(self.boss).values_list('pk', flat=True))
        self.assertEqual(len(ids), 3)
        self.assertTrue(lock.describe(Task.objects.get(pk=next(iter(ids))))['own'])
        self.assertFalse(lock.describe(self.make('HIGH', overdue=9))['own'])         # one somebody else allotted

    def test_each_person_only_sees_their_own(self):
        mine = self.make(overdue=5)
        self.assertEqual(list(lock.locked_tasks(self.worker)), [mine])
        self.assertEqual(list(lock.locked_tasks(self.other)), [])
        self.assertEqual(list(lock.tasks_to_unlock(self.boss)), [mine])           # the creator's list
        self.assertEqual(list(lock.tasks_to_unlock(self.worker)), [])

    def test_the_day_can_be_given_for_checking(self):
        task = self.make('HIGH', overdue=1)
        self.assertFalse(lock.is_locking(task))
        self.assertTrue(lock.is_locking(task, today=TODAY + datetime.timedelta(days=2)))
        self.assertEqual(lock.describe(task, today=TODAY + datetime.timedelta(days=2))['days'], 3)


class TheGateTests(LockBase):
    def setUp(self):
        super().setUp()
        self.task = self.make('HIGH', overdue=5)

    def test_a_locked_user_is_sent_to_the_lock_page_from_every_screen(self):
        client = self.client_for(self.worker)
        for url in ('/order/joblist/', '/task/list/', '/task/addtask/', '/crm/', '/manpower/shiftlist/'):
            response = client.get(url)
            self.assertEqual((response.status_code, response['Location']), (302, LOCKED_URL), url)

    def test_scripts_and_the_api_get_a_403_they_can_read(self):
        client = self.client_for(self.worker)
        response = client.get('/api/order/job-nav-summary/')
        self.assertEqual((response.status_code, response.json()['code']), (403, 'tasks_locked'))
        ajax = client.get('/order/joblist/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual((ajax.status_code, ajax.json()['url']), (403, LOCKED_URL))

    def test_what_a_locked_user_can_still_reach(self):
        client = self.client_for(self.worker)
        self.assertEqual(client.get(LOCKED_URL).status_code, 200)
        self.assertEqual(client.get(f'/task/detail/{self.task.pk}/').status_code, 200)
        logout = client.get('/logout/')
        self.assertNotEqual(logout.get('Location'), LOCKED_URL)                      # logging out is never blocked
        self.assertNotEqual(client.get('/api/task/tasks/nav-summary/').json().get('code'), 'tasks_locked')

    def test_chat_and_asking_to_close_still_work(self):
        client = self.client_for(self.worker)
        sent = client.post(f'/task/message/{self.task.pk}/', {'msg_text': 'Waiting for material'})
        self.assertEqual(sent.status_code, 200)
        self.assertTrue(TaskMsg.objects.filter(task=self.task, msg_text='Waiting for material').exists())
        client.post(f'/task/requesttoclose/{self.task.pk}/', {'request_to_close': 'on'})
        self.assertTrue(Task.objects.get(pk=self.task.pk).request_to_close)
        self.assertEqual(client.get('/order/joblist/').status_code, 200)         # asking to close frees them

    def test_other_people_and_unlocked_users_are_not_touched(self):
        self.assertEqual(self.client_for(self.other).get('/order/joblist/').status_code, 200)
        self.assertEqual(self.client_for(self.boss).get('/order/joblist/').status_code, 200)

    def test_nobody_logged_in_is_not_affected(self):
        response = Client().get('/order/joblist/')
        self.assertIn('/login/', response['Location'])

    def test_a_task_within_its_limit_locks_nothing(self):
        Task.objects.filter(taskname__startswith='LOCKTEST').delete()
        self.make('HIGH', overdue=2)
        self.assertEqual(self.client_for(self.worker).get('/order/joblist/').status_code, 200)

    def test_being_locked_is_noticed_straight_away_and_clearing_is_trusted_briefly(self):
        with mock.patch('task.lock.CACHE_SECONDS', 60):
            Task.objects.filter(taskname__startswith='LOCKTEST').delete()
            client = self.client_for(self.worker)
            self.assertEqual(client.get('/order/joblist/').status_code, 200)           # clear, remembered 60 s
            self.make('HIGH', overdue=5)
            self.assertEqual(client.get('/task/list/').status_code, 200)               # other pages: still trusted
            self.assertEqual(client.get('/order/joblist/').status_code, 302)           # the job list (and its popup) never is
            session = client.session
            session[lock.SESSION_KEY] = 0                                               # the 60 s are over
            session.save()
            self.assertEqual(client.get('/task/list/').status_code, 302)
            Task.objects.filter(taskname__startswith='LOCKTEST').update(target_date=when(0))   # creator moves the date
            self.assertEqual(client.get('/order/joblist/').status_code, 200)           # locked is never cached


class TheLockPageTests(LockBase):
    def test_it_names_the_tasks_who_allotted_them_and_how_late(self):
        task = self.make('NORMAL', overdue=5)
        html = self.client_for(self.worker).get(LOCKED_URL).content.decode()
        self.assertIn(task.taskname, html)
        self.assertIn('Bossy', html)
        self.assertIn('5 days', html)
        self.assertIn('limit 3', html)
        self.assertIn(reverse('task:askdate', kwargs={'id': task.pk}), html)

    def test_somebody_not_locked_and_with_nothing_to_fix_goes_back_to_work(self):
        response = self.client_for(self.other).get(LOCKED_URL)
        self.assertEqual((response.status_code, response['Location']), (302, '/order/joblist/'))

    def test_a_creator_sees_the_tasks_they_need_to_give_a_new_date(self):
        task = self.make('LOW', overdue=8)
        html = self.client_for(self.boss).get(LOCKED_URL).content.decode()
        self.assertIn('Tasks you allotted', html)
        self.assertIn(reverse('task:changedate', kwargs={'id': task.pk}), html)
        self.assertNotIn('You cannot continue', html)                                # the creator is not locked

    def test_a_locked_creator_can_still_free_the_people_they_locked(self):
        self.make('HIGH', overdue=5, who=self.boss, by=self.other)                  # boss is locked by 'other'
        theirs = self.make('HIGH', overdue=5, who=self.worker, by=self.boss)        # and has locked the worker
        client = self.client_for(self.boss)
        self.assertEqual(client.get('/order/joblist/').status_code, 302)
        response = client.post(f'/task/changedate/{theirs.pk}/', {'target_date': (TODAY + datetime.timedelta(days=2)).isoformat()})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client_for(self.worker).get('/order/joblist/').status_code, 200)

    def test_asked_already_is_shown(self):
        task = self.make(overdue=5)
        client = self.client_for(self.worker)
        client.post(reverse('task:askdate', kwargs={'id': task.pk}))
        self.assertIn('Asked', client.get(LOCKED_URL).content.decode())


class TheTaskPageTests(LockBase):
    def detail(self, user, task):
        return self.client_for(user).get(f'/task/detail/{task.pk}/').content.decode()

    def test_the_assignee_is_told_why_and_how_to_get_out(self):
        task = self.make('HIGH', overdue=4)
        html = ' '.join(self.detail(self.worker, task).split())                      # the template wraps lines
        self.assertIn('id="lockBox"', html)
        self.assertIn('4 days overdue', html)
        self.assertIn('2 days allowed for HIGH', html)
        self.assertIn('id="askDateButton"', html)
        self.assertNotIn('id="laterButton"', html)                                   # no Later: the date must change

    def test_the_creator_gets_the_date_control_with_a_warning_when_it_locks(self):
        task = self.make('HIGH', overdue=4)
        html = self.detail(self.boss, task)
        self.assertIn('id="changeDateBox"', html)
        self.assertIn('is locked out by this task', html)
        self.assertNotIn('id="lockBox"', html)

    def test_the_creator_can_change_the_date_of_any_open_task_without_a_warning(self):
        task = self.make('LOW', overdue=-5)
        html = self.detail(self.boss, task)
        self.assertIn('id="changeDateBox"', html)
        self.assertNotIn('is locked out', html)

    def test_the_creator_of_a_task_they_gave_themselves_can_change_its_date_too(self):
        own = self.make(who=self.boss, by=self.boss)
        html = self.detail(self.boss, own)
        self.assertIn('id="changeDateBox"', html)
        self.assertNotIn('is locked out', html)                                       # a self-assigned task never locks

    def test_no_date_control_for_closed_tasks_or_people_who_did_not_create_the_task(self):
        self.assertNotIn('changeDateBox', self.detail(self.boss, self.make(is_closed=True)))
        self.assertNotIn('changeDateBox', self.detail(self.worker, self.make(overdue=-3)))
        self.assertNotIn('lockBox', self.detail(self.worker, self.make('HIGH', overdue=2)))


class ChangeDateTests(LockBase):
    def change(self, user, task, value, **extra):
        return self.client_for(user).post(f'/task/changedate/{task.pk}/', {'target_date': value, **extra})

    def test_the_creator_gives_a_new_date_and_it_frees_the_assignee(self):
        task = self.make('HIGH', overdue=5)
        new = (TODAY + datetime.timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
        response = self.change(self.boss, task, new)
        self.assertEqual(response.status_code, 302)
        task.refresh_from_db()
        self.assertEqual(task.target_date, datetime.datetime.strptime(new, '%Y-%m-%dT%H:%M'))
        self.assertEqual(task.editedby, self.boss)
        self.assertFalse(lock.is_locking(task))
        self.assertEqual(self.client_for(self.worker).get('/order/joblist/').status_code, 200)

    def test_it_is_written_in_the_chat_and_the_assignee_is_told(self):
        task = self.make('HIGH', overdue=5)
        self.change(self.boss, task, (TODAY + datetime.timedelta(days=3)).isoformat())
        note = TaskMsg.objects.get(task=task)
        self.assertIn('Target date changed from', note.msg_text)
        self.assertEqual(note.createdby, self.boss)
        told = Notification.objects.get(user=self.worker, task=task)
        self.assertIn('changed the target date', told.message)

    def test_a_date_alone_keeps_the_old_time_of_day(self):
        task = self.make('LOW', overdue=-1)                                          # target at 12:00
        self.change(self.boss, task, (TODAY + datetime.timedelta(days=9)).isoformat())
        task.refresh_from_db()
        self.assertEqual((task.target_date.date(), task.target_date.hour), (TODAY + datetime.timedelta(days=9), 12))

    def test_today_is_allowed_the_past_is_not(self):
        task = self.make('HIGH', overdue=5)
        self.assertEqual(self.change(self.boss, task, when(1).isoformat()).status_code, 302)
        self.assertEqual(Task.objects.get(pk=task.pk).target_date, when(5))          # refused: unchanged
        self.change(self.boss, task, TODAY.isoformat())
        self.assertEqual(Task.objects.get(pk=task.pk).target_date.date(), TODAY)

    def test_rubbish_dates_are_refused(self):
        task = self.make('HIGH', overdue=5)
        for text in ('', 'tomorrow', '31/02/2030', '2030-13-45'):
            self.change(self.boss, task, text)
        self.assertEqual(Task.objects.get(pk=task.pk).target_date, when(5))
        self.assertFalse(TaskMsg.objects.filter(task=task).exists())

    def test_only_the_creator_of_the_task_may_change_its_date(self):
        task = self.make('HIGH', overdue=5)
        future = (TODAY + datetime.timedelta(days=5)).isoformat()
        for user in (self.worker, self.other):                                       # the assignee cannot move it themselves
            self.change(user, task, future)
        self.assertEqual(Task.objects.get(pk=task.pk).target_date, when(5))
        self.assertFalse(TaskMsg.objects.filter(task=task).exists())

    def test_a_task_the_creator_gave_themselves_can_have_its_date_changed_without_telling_anyone(self):
        own = self.make(who=self.boss, by=self.boss)
        future = TODAY + datetime.timedelta(days=5)
        self.assertEqual(self.change(self.boss, own, future.isoformat()).status_code, 302)
        self.assertEqual(Task.objects.get(pk=own.pk).target_date.date(), future)
        self.assertFalse(Notification.objects.filter(task=own).exists())             # nobody else to tell
        self.assertTrue(TaskMsg.objects.filter(task=own).exists())                   # still noted in the chat

    def test_any_open_task_the_user_created_can_be_moved_earlier_or_later(self):
        task = self.make('LOW', overdue=-10)                                          # due in 10 days
        sooner = TODAY + datetime.timedelta(days=2)
        self.change(self.boss, task, sooner.isoformat())
        self.assertEqual(Task.objects.get(pk=task.pk).target_date.date(), sooner)
        later = TODAY + datetime.timedelta(days=30)
        self.change(self.boss, task, later.isoformat())
        self.assertEqual(Task.objects.get(pk=task.pk).target_date.date(), later)
        self.assertEqual(TaskMsg.objects.filter(task=task).count(), 2)

    def test_a_date_that_is_not_a_real_date_is_reported_not_a_crash(self):
        task = self.make('HIGH', overdue=5)
        response = self.change(self.boss, task, '2030-13-45')
        self.assertEqual(response.status_code, 302)
        self.assertIn('valid target date', [str(m) for m in response.wsgi_request._messages][0])

    def test_a_closed_task_keeps_its_date(self):
        task = self.make(overdue=5, is_closed=True)
        self.change(self.boss, task, (TODAY + datetime.timedelta(days=5)).isoformat())
        self.assertEqual(Task.objects.get(pk=task.pk).target_date, when(5))

    def test_it_only_goes_back_to_our_own_pages(self):
        task = self.make('HIGH', overdue=5)
        future = (TODAY + datetime.timedelta(days=5)).isoformat()
        evil = self.change(self.boss, task, future, next='https://evil.example/')
        self.assertEqual(evil['Location'], f'/task/detail/{task.pk}/')
        task2 = self.make('HIGH', overdue=5)
        good = self.change(self.boss, task2, future, next=LOCKED_URL)
        self.assertEqual(good['Location'], LOCKED_URL)

    def test_only_a_post_works(self):
        task = self.make('HIGH', overdue=5)
        self.assertEqual(self.client_for(self.boss).get(f'/task/changedate/{task.pk}/').status_code, 405)


class AskForANewDateTests(LockBase):
    def ask(self, user, task):
        return self.client_for(user).post(f'/task/askdate/{task.pk}/')

    def test_the_assignee_asks_and_the_creator_is_told(self):
        task = self.make('HIGH', overdue=5)
        self.ask(self.worker, task)
        message = TaskMsg.objects.get(task=task)
        self.assertEqual(message.createdby, self.worker)
        self.assertTrue(message.msg_text.startswith('Please change the target date'))
        self.assertIn('5 day(s) overdue', message.msg_text)
        told = Notification.objects.get(user=self.boss, task=task)
        self.assertIn('asks you to change the target date', told.message)

    def test_asking_twice_in_an_hour_sends_one_request(self):
        task = self.make('HIGH', overdue=5)
        self.ask(self.worker, task)
        self.ask(self.worker, task)
        self.assertEqual(TaskMsg.objects.filter(task=task).count(), 1)
        self.assertEqual(Notification.objects.filter(task=task).count(), 1)

    def test_after_an_hour_they_may_ask_again(self):
        task = self.make('HIGH', overdue=5)
        self.ask(self.worker, task)
        TaskMsg.objects.filter(task=task).update(created=datetime.datetime.now() - datetime.timedelta(minutes=61))
        self.ask(self.worker, task)
        self.assertEqual(TaskMsg.objects.filter(task=task).count(), 2)

    def test_only_the_assignee_of_an_open_task_can_ask(self):
        task = self.make('HIGH', overdue=5)
        self.assertEqual(self.ask(self.boss, task).status_code, 404)
        self.assertEqual(self.ask(self.other, task).status_code, 404)
        self.assertEqual(self.ask(self.worker, self.make(is_closed=True)).status_code, 404)
        own = self.make(who=self.boss, by=self.boss)
        self.ask(self.boss, own)
        self.assertFalse(TaskMsg.objects.filter(task=own).exists())


class LaterIsNotForLockingTasksTests(LockBase):
    def started(self):
        client = self.client_for(self.worker)
        session = client.session
        popup.start_review(session)
        session.save()
        return client

    def test_later_is_refused_when_the_task_locks(self):
        task = self.make('HIGH', overdue=5)
        client = self.started()
        ajax = client.post(f'/task/later/{task.pk}/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(ajax.status_code, 403)                                      # the gate answers before the view

    def test_even_past_the_gate_it_is_not_recorded(self):
        task = self.make('HIGH', overdue=5)
        session = FakeSession()
        popup.start_review(session)
        self.assertFalse(popup.can_postpone(self.worker, session, task))
        popup.postpone(self.worker, session, task)
        self.assertNotIn(task.pk, popup.postponed_ids(session))

    def test_within_the_limit_later_still_works(self):
        task = self.make('HIGH', overdue=2)
        session = FakeSession()
        popup.start_review(session)
        self.assertTrue(popup.can_postpone(self.worker, session, task))


class NoLaterForATaskThatLocksTests(LockBase):
    """A task past its limit must never offer Later: the user would click it and carry on working."""

    def setUp(self):
        super().setUp()
        self.locking = self.make('HIGH', overdue=5)                 # past its 2 days
        self.within = self.make('HIGH', overdue=1)                  # overdue, but still within its limit
        self.upcoming = self.make('LOW', overdue=-4)

    def stale_all_clear_client(self):
        """A session the lock trusts as 'nothing is locked' for the next minute, with the login popup due."""
        import time as time_module
        client = self.client_for(self.worker)
        session = client.session
        session[lock.SESSION_KEY] = time_module.time() + 600
        session['show_pending_tasks'] = True
        session.save()
        return client

    def test_a_locked_user_is_never_shown_the_popup_even_with_a_stale_all_clear(self):
        response = self.stale_all_clear_client().get('/order/joblist/')
        self.assertEqual((response.status_code, response['Location']), (302, LOCKED_URL))

    def test_the_tasks_in_the_popup_know_which_ones_lock(self):
        flags = {t.pk: t.locks for t in popup.login_popup_tasks(self.worker)}
        self.assertEqual(flags, {self.locking.pk: True, self.within.pk: False, self.upcoming.pk: False})

    def test_even_if_the_popup_is_drawn_a_locking_task_has_no_later_button(self):
        client = self.stale_all_clear_client()
        with mock.patch('order.views.locked_tasks', return_value=Task.objects.none()):     # get past the view's own check
            html = client.get('/order/joblist/').content.decode()
        start = html.index('id="pendingTasksModal"')
        popup_html = html[start:html.index('Dismiss</button>', start)]
        self.assertNotIn(f'data-task-id="{self.locking.pk}"', popup_html)                 # no Later for the locking task
        self.assertIn('Locked: needs a new date', popup_html)
        self.assertIn(f'data-task-id="{self.within.pk}"', popup_html)                     # the one within its limit still has it
        self.assertEqual(popup_html.count('later-btn" data-task-id'), 1)

    def test_the_locking_task_page_has_no_later_either_only_asking_for_a_date(self):
        client = self.client_for(self.worker)
        session = client.session
        popup.start_review(session)
        session.save()
        html = client.get(f'/task/detail/{self.locking.pk}/').content.decode()
        self.assertNotIn('id="laterButton"', html)
        self.assertNotIn('id="laterBox"', html)
        self.assertIn('id="askDateButton"', html)

    def test_later_cannot_be_recorded_for_it_by_any_route(self):
        client = self.client_for(self.worker)
        self.assertEqual(client.post(f'/task/later/{self.locking.pk}/', HTTP_X_REQUESTED_WITH='XMLHttpRequest').status_code, 403)
        session = FakeSession()
        popup.start_review(session)
        popup.postpone(self.worker, session, self.locking)
        self.assertNotIn(self.locking.pk, popup.postponed_ids(session))

    def test_the_other_due_task_is_out_of_reach_while_locked(self):
        client = self.client_for(self.worker)
        for url in ('/order/joblist/', f'/task/later/{self.within.pk}/'):
            response = client.post(url) if 'later' in url else client.get(url)
            self.assertIn(response.status_code, (302, 403), url)
        self.assertFalse(popup.postponed_ids(client.session))

    def test_while_locked_no_other_task_offers_later_either(self):
        client = self.client_for(self.worker)
        session = client.session
        popup.start_review(session)                                  # a review that was already under way
        session.save()
        html = client.get(f'/task/detail/{self.within.pk}/').content.decode()
        self.assertNotIn('id="laterButton"', html)                   # the other due task: no Later while locked
        self.assertFalse(popup.can_postpone(self.worker, client.session, self.within))
        fake = {}
        popup.start_review(fake)
        popup.postpone(self.worker, fake, self.within)
        self.assertNotIn(self.within.pk, popup.postponed_ids(fake))

    def test_free_again_once_the_date_is_changed_later_works_again(self):
        client = self.client_for(self.worker)
        session = client.session
        popup.start_review(session)
        session.save()
        Task.objects.filter(pk=self.locking.pk).update(target_date=when(0))       # the creator moved the date
        self.assertTrue(popup.can_postpone(self.worker, client.session, self.within))
        self.assertIn('id="laterButton"', client.get(f'/task/detail/{self.within.pk}/').content.decode())


class TasksYouAllottedToYourselfTests(LockBase):
    """The case from the screenshot: TEST (HIGH, 5 days overdue) and TEST-2, both allotted by the user to themselves."""

    def setUp(self):
        super().setUp()
        self.test = self.make('HIGH', overdue=5, who=self.boss, by=self.boss)          # past its 2 days
        self.test2 = self.make('LOW', overdue=-1, who=self.boss, by=self.boss)         # due tomorrow

    def stale_client(self):
        """A session the lock trusts as clear, with the login popup due (how the popup could slip through)."""
        import time as time_module
        client = self.client_for(self.boss)
        session = client.session
        session[lock.SESSION_KEY] = time_module.time() + 600
        session['show_pending_tasks'] = True
        session.save()
        return client

    def test_the_user_is_locked_and_sent_to_the_lock_page(self):
        client = self.client_for(self.boss)
        response = client.get('/order/joblist/')
        self.assertEqual((response.status_code, response['Location']), (302, LOCKED_URL))

    def test_no_popup_and_no_later_even_with_a_stale_all_clear(self):
        response = self.stale_client().get('/order/joblist/')
        self.assertEqual((response.status_code, response['Location']), (302, LOCKED_URL))

    def test_the_popup_list_marks_it_as_locking_so_it_cannot_draw_a_later_button(self):
        flags = {t.taskname: t.locks for t in popup.login_popup_tasks(self.boss)}
        self.assertTrue(flags[self.test.taskname])
        self.assertFalse(flags[self.test2.taskname])
        with mock.patch('order.views.locked_tasks', return_value=Task.objects.none()):     # force the popup to be drawn
            html = self.stale_client().get('/order/joblist/').content.decode()
        popup_html = html[html.index('id="pendingTasksModal"'):]
        popup_html = popup_html[:popup_html.index('Dismiss</button>')]
        self.assertNotIn(f'data-task-id="{self.test.pk}"', popup_html)
        self.assertIn('Locked: needs a new date', popup_html)

    def test_the_lock_page_lets_them_set_the_date_themselves(self):
        html = self.client_for(self.boss).get(LOCKED_URL).content.decode()
        self.assertIn('own-date-form', html)
        self.assertIn('allotted to yourself', html)
        self.assertNotIn('ask-date', html)                                              # nobody else to ask
        self.assertIn(reverse('task:changedate', kwargs={'id': self.test.pk}), html)

    def test_the_task_page_says_so_and_has_the_date_box_but_no_ask_and_no_later(self):
        html = ' '.join(self.client_for(self.boss).get(f'/task/detail/{self.test.pk}/').content.decode().split())
        self.assertIn('id="lockBox"', html)
        self.assertIn('until you give it a new target date', html)
        self.assertNotIn('id="askDateButton"', html)
        self.assertNotIn('id="laterButton"', html)
        self.assertIn('id="changeDateBox"', html)
        self.assertNotIn('is locked out by this task', html)                            # that wording is for somebody else

    def test_setting_a_new_date_frees_them_and_the_popup_returns(self):
        client = self.client_for(self.boss)
        session = client.session
        session['show_pending_tasks'] = True
        session.save()
        client.get('/order/joblist/')                                                    # locked: redirected, flag kept
        new = (TODAY + datetime.timedelta(days=2)).isoformat()
        response = client.post(f'/task/changedate/{self.test.pk}/', {'target_date': new, 'next': LOCKED_URL})
        self.assertEqual(response['Location'], LOCKED_URL)
        free = client.get('/order/joblist/')
        self.assertEqual(free.status_code, 200)
        self.assertEqual(Task.objects.get(pk=self.test.pk).target_date.date(), TODAY + datetime.timedelta(days=2))

    def test_a_task_they_allotted_to_themselves_but_still_within_its_limit_does_not_lock(self):
        Task.objects.filter(pk=self.test.pk).update(target_date=when(2))                 # 2 days: allowed for HIGH
        self.assertEqual(self.client_for(self.boss).get('/order/joblist/').status_code, 200)

    def test_asking_somebody_for_a_date_is_still_refused_when_there_is_nobody_else(self):
        client = self.client_for(self.boss)
        client.post(f'/task/askdate/{self.test.pk}/')
        self.assertFalse(TaskMsg.objects.filter(task=self.test).exists())
