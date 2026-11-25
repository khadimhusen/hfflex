"""The due-task review and the overdue lock through the API (what the frontend uses)."""
import datetime
import time
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from task import lock
from task.models import Notification, Task, TaskMsg

TODAY = datetime.date.today()


def when(days_from_today, hour=12):
    return datetime.datetime.combine(TODAY + datetime.timedelta(days=days_from_today), datetime.time(hour, 0))


class ApiBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.boss = User.objects.create_user('apiboss', 'a@example.com', 'x', first_name='Bossy')
        cls.worker = User.objects.create_user('apiworker', 'b@example.com', 'x')
        cls.other = User.objects.create_user('apiother', 'c@example.com', 'x')

    def setUp(self):
        patcher = mock.patch('task.lock.CACHE_SECONDS', 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def make(self, days=0, priority='NORMAL', who=None, by=None, **extra):
        """A task whose target date is `days` from today (negative = overdue)."""
        return Task.objects.create(taskname=f'APITEST {priority} {days}', description='x', priority=priority,
                                   target_date=when(days), task_alloted_to=who or self.worker,
                                   createdby=by if by is not None else self.boss, **extra)

    def api(self, user, fresh=False):
        client = APIClient()
        client.force_login(user)
        if fresh:
            client.get('/api/task/review/', {'fresh': 1})
        return client

    def review(self, client, **params):
        return client.get('/api/task/review/', params).json()


class ReviewTests(ApiBase):
    def test_a_fresh_login_lists_the_due_tasks_then_the_upcoming_ones(self):
        self.make(-1), self.make(0), self.make(2), self.make(5)
        client = APIClient()
        client.force_login(self.worker)
        data = self.review(client, fresh=1)
        self.assertTrue(data['show'])
        self.assertEqual([t['is_due'] for t in data['tasks']], [True, True, False, False])
        self.assertEqual(data['due_left'], 2)
        self.assertFalse(data['locked'])

    def test_each_row_says_how_overdue_it_is_and_who_gave_it(self):
        self.make(-2)
        client = APIClient()
        client.force_login(self.worker)
        row = self.review(client, fresh=1)['tasks'][0]
        self.assertEqual((row['days_overdue'], row['limit_days'], row['locks']), (2, 3, False))
        self.assertEqual(row['createdby_name'], 'Bossy')
        self.assertFalse(row['own'])

    def test_without_a_fresh_login_nothing_is_shown(self):
        self.make(-1)
        client = APIClient()
        client.force_login(self.worker)
        self.assertFalse(self.review(client)['show'])

    def test_it_keeps_coming_back_until_every_due_task_is_put_off(self):
        first, second = self.make(-1), self.make(0)
        client = APIClient()
        client.force_login(self.worker)
        self.assertTrue(self.review(client, fresh=1)['show'])
        self.assertTrue(self.review(client)['show'])                              # no flag needed any more
        self.assertEqual(client.post(f'/api/task/review/later/{first.pk}/').json(), {'remaining': 1})
        data = self.review(client)
        self.assertTrue(data['show'])
        self.assertEqual([t['id'] for t in data['tasks'] if t['is_due']], [second.pk])
        self.assertEqual(client.post(f'/api/task/review/later/{second.pk}/').json(), {'remaining': 0})
        self.assertFalse(self.review(client)['show'])

    def test_only_upcoming_tasks_make_an_ordinary_popup_that_is_shown_once(self):
        self.make(3)
        client = APIClient()
        client.force_login(self.worker)
        data = self.review(client, fresh=1)
        self.assertTrue(data['show'])
        self.assertEqual(data['due_left'], 0)
        self.assertFalse(self.review(client)['show'])

    def test_a_slow_request_saving_an_old_copy_of_the_session_cannot_end_the_review(self):
        # The frontend sends several requests at once and every one saves the whole session; one that
        # loaded it before the review started used to save over it and silently end the review.
        self.make(-1)
        client = APIClient()
        client.force_login(self.worker)
        stale = client.session                                    # a request that loaded the session early
        list(stale.keys())                                        # (the session loads when first looked at)
        self.assertTrue(self.review(client, fresh=1)['show'])     # the review starts meanwhile
        stale['last_request'] = time.time()
        stale.save()                                              # ... and the slow one saves its old copy
        data = self.review(client)
        self.assertTrue(data['show'])
        self.assertEqual(data['due_left'], 1)

    def test_nothing_pending_nothing_shown(self):
        client = APIClient()
        client.force_login(self.worker)
        self.assertFalse(self.review(client, fresh=1)['show'])

    def test_closed_tasks_and_other_peoples_tasks_are_left_out(self):
        self.make(-1, is_closed=True)
        self.make(-1, who=self.other)
        client = APIClient()
        client.force_login(self.worker)
        self.assertEqual(self.review(client, fresh=1)['tasks'], [])

    def test_a_locked_user_gets_the_lock_state_not_the_popup(self):
        stuck = self.make(-5)                                 # NORMAL, limit 3 days
        self.make(-1)
        client = APIClient()
        client.force_login(self.worker)
        data = self.review(client, fresh=1)
        self.assertTrue(data['locked'])
        self.assertFalse(data['show'])
        self.assertEqual([t['id'] for t in data['locked_tasks']], [stuck.pk])
        self.assertTrue(data['locked_tasks'][0]['locks'])

    def test_once_freed_the_popup_that_was_waiting_comes_up(self):
        stuck = self.make(-5)
        client = APIClient()
        client.force_login(self.worker)
        self.assertTrue(self.review(client, fresh=1)['locked'])
        stuck.target_date = when(1)
        stuck.save()
        data = self.review(client)
        self.assertFalse(data['locked'])
        self.assertTrue(data['show'])

    def test_a_creator_is_shown_the_tasks_that_lock_somebody_else(self):
        stuck = self.make(-5)
        data = self.review(self.api(self.boss))
        self.assertEqual([t['id'] for t in data['to_fix']], [stuck.pk])
        self.assertFalse(data['locked'])

    def test_it_needs_a_login(self):
        self.assertIn(APIClient().get('/api/task/review/').status_code, (401, 403))


class LaterTests(ApiBase):
    def test_a_task_that_is_not_due_cannot_be_put_off(self):
        task = self.make(2)
        client = self.api(self.worker, fresh=True)
        response = client.post(f'/api/task/review/later/{task.pk}/')
        self.assertEqual(response.status_code, 400)

    def test_nobody_puts_off_somebody_elses_task(self):
        task = self.make(-1, who=self.other)
        self.assertEqual(self.api(self.worker, fresh=True).post(f'/api/task/review/later/{task.pk}/').status_code, 404)

    def test_a_task_past_its_limit_cannot_be_put_off(self):
        task = self.make(-5)
        response = self.api(self.worker, fresh=True).post(f'/api/task/review/later/{task.pk}/')
        self.assertEqual(response.status_code, 400)
        self.assertIn('new target date', response.json()['detail'])

    def test_a_closed_task_is_not_found(self):
        task = self.make(-1, is_closed=True)
        self.assertEqual(self.api(self.worker, fresh=True).post(f'/api/task/review/later/{task.pk}/').status_code, 404)


class LockStateTests(ApiBase):
    def state(self, user, task, fresh=True):
        return self.api(user, fresh=fresh).get(f'/api/task/tasks/{task.pk}/lock-state/').json()

    def test_a_due_task_offers_later_during_the_review(self):
        task = self.make(-1)
        self.assertTrue(self.state(self.worker, task)['show_later'])

    def test_no_later_without_a_review_or_for_the_creator(self):
        task = self.make(-1)
        self.assertFalse(self.state(self.worker, task, fresh=False)['show_later'])
        self.assertFalse(self.state(self.boss, task)['show_later'])

    def test_a_task_that_locks_its_assignee_says_so_and_offers_no_later(self):
        task = self.make(-5)
        state = self.state(self.worker, task)
        self.assertFalse(state['show_later'])
        self.assertEqual(state['lock'], {'days': 5, 'limit': 3, 'own': False})
        self.assertFalse(state['can_change_date'])

    def test_the_creator_can_change_the_date_and_sees_who_is_locked(self):
        task = self.make(-5)
        state = self.state(self.boss, task)
        self.assertTrue(state['can_change_date'])
        self.assertTrue(state['creator_sees_locked'])
        self.assertIsNone(state['lock'])

    def test_a_task_you_gave_yourself_locks_you_and_you_change_the_date_yourself(self):
        task = self.make(-5, who=self.boss)
        state = self.state(self.boss, task)
        self.assertEqual(state['lock'], {'days': 5, 'limit': 3, 'own': True})
        self.assertTrue(state['can_change_date'])
        self.assertFalse(state['creator_sees_locked'])

    def test_it_names_both_people_even_without_full_names(self):
        task = self.make(-5)
        state = self.state(self.boss, task)
        self.assertEqual((state['creator_name'], state['assignee_name']), ('Bossy', 'apiworker'))

    def test_a_stranger_cannot_look(self):
        task = self.make(-5)
        self.assertIn(self.api(self.other).get(f'/api/task/tasks/{task.pk}/lock-state/').status_code, (403, 404))


class ChangeDateApiTests(ApiBase):
    def post(self, user, task, value):
        return self.api(user).post(f'/api/task/tasks/{task.pk}/change-date/', {'target_date': value}, format='json')

    def test_the_creator_gives_a_new_date_which_frees_the_assignee(self):
        task = self.make(-5)
        self.assertTrue(lock.locked_tasks(self.worker).exists())
        new = when(2)
        response = self.post(self.boss, task, new.strftime('%Y-%m-%dT%H:%M'))
        self.assertEqual(response.status_code, 200, response.content)
        task.refresh_from_db()
        self.assertEqual(task.target_date, new)
        self.assertFalse(lock.locked_tasks(self.worker).exists())
        self.assertTrue(TaskMsg.objects.filter(task=task, msg_text__startswith='Target date changed').exists())
        self.assertTrue(Notification.objects.filter(user=self.worker, task=task).exists())

    def test_only_the_creator_may(self):
        task = self.make(-5)
        response = self.post(self.worker, task, when(2).strftime('%Y-%m-%dT%H:%M'))
        self.assertEqual(response.status_code, 403)
        task.refresh_from_db()
        self.assertEqual(task.target_date, when(-5))

    def test_a_past_or_invalid_date_is_refused(self):
        task = self.make(-5)
        for bad in (when(-1).strftime('%Y-%m-%dT%H:%M'), '', 'nonsense', '2030-13-45'):
            response = self.post(self.boss, task, bad)
            self.assertEqual(response.status_code, 400, bad)
            self.assertIn('detail', response.json())

    def test_a_closed_task_keeps_its_date(self):
        task = self.make(-5, is_closed=True)
        self.assertEqual(self.post(self.boss, task, when(2).strftime('%Y-%m-%dT%H:%M')).status_code, 400)

    def test_a_task_you_gave_yourself_notifies_nobody(self):
        task = self.make(-5, who=self.boss)
        self.assertEqual(self.post(self.boss, task, when(1).strftime('%Y-%m-%dT%H:%M')).status_code, 200)
        self.assertFalse(Notification.objects.filter(task=task).exists())


class AskDateApiTests(ApiBase):
    def ask(self, user, task):
        return self.api(user).post(f'/api/task/tasks/{task.pk}/ask-date/')

    def test_the_assignee_asks_and_the_creator_is_told(self):
        task = self.make(-5)
        response = self.ask(self.worker, task)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.assertTrue(TaskMsg.objects.filter(task=task, createdby=self.worker, msg_text__startswith='Please change').exists())
        self.assertTrue(Notification.objects.filter(user=self.boss, task=task).exists())

    def test_asking_twice_in_an_hour_does_not_pile_up(self):
        task = self.make(-5)
        self.ask(self.worker, task)
        response = self.ask(self.worker, task)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['ok'])
        self.assertEqual(TaskMsg.objects.filter(task=task, msg_text__startswith='Please change').count(), 1)

    def test_nobody_else_to_ask_when_you_gave_it_to_yourself(self):
        task = self.make(-5, who=self.boss)
        self.assertEqual(self.ask(self.boss, task).status_code, 400)

    def test_the_creator_is_not_the_one_who_asks(self):
        task = self.make(-5)
        r = self.ask(self.boss, task); self.assertEqual(r.status_code, 403, r.content[:300])


class TheGateTests(ApiBase):
    def test_a_locked_user_can_still_reach_the_task_pages_and_the_review(self):
        task = self.make(-5)
        client = self.api(self.worker)
        self.assertEqual(client.get('/api/task/review/').status_code, 200)
        self.assertEqual(client.get(f'/api/task/tasks/{task.pk}/').status_code, 200)
        self.assertEqual(client.get(f'/api/task/tasks/{task.pk}/lock-state/').status_code, 200)

    def test_everything_else_says_the_user_is_locked(self):
        self.make(-5)
        response = self.api(self.worker).get('/api/customer/customers/')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'tasks_locked')

    def test_a_locked_user_can_still_log_out(self):
        self.make(-5)
        client = self.api(self.worker)
        self.assertEqual(client.post('/api/crm/logout/').status_code, 200)
        self.assertEqual(client.get('/api/task/review/').status_code, 403)         # really logged out now
