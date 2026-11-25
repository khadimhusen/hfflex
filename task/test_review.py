"""Going through the due tasks: the review that starts with the login pop-up."""
import datetime
import itertools

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from task import popup
from task.models import Task

TODAY = datetime.date.today()
LATER = 'class="btn btn-outline-secondary btn-sm later-btn"'


def at(days, hour=12):
    return datetime.datetime.combine(TODAY + datetime.timedelta(days=days), datetime.time(hour, 0))


class FakeSession(dict):
    """Stands in for a login's session: only its key matters to the review."""
    modified = False
    counter = itertools.count(1)

    def __init__(self):
        super().__init__()
        self.session_key = f'fakesessionkey{next(self.counter):08d}'


class ReviewBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.boss = User.objects.create_user('revboss', 'a@example.com', 'x')
        cls.user = User.objects.create_user('revuser', 'b@example.com', 'x')
        cls.stranger = User.objects.create_user('revstranger', 'c@example.com', 'x')

        def make(name, when, who=cls.user, **extra):
            return Task.objects.create(taskname=f'REVTEST {name}', description='x', target_date=when,
                                       task_alloted_to=who, createdby=cls.boss, **extra)
        cls.a = make('A overdue', at(-3))
        cls.b = make('B overdue', at(-1))
        cls.c = make('C today', datetime.datetime.combine(TODAY, datetime.time(23, 59)))
        cls.future = make('D future', at(4))
        cls.others = make('E somebody elses', at(-2), who=cls.stranger)
        cls.closed = make('F closed', at(-5), is_closed=True)

    def logged_in(self, user=None):
        client = Client()
        client.force_login(user or self.user)
        return client

    def login_flag(self, client):
        session = client.session
        session['show_pending_tasks'] = True
        session.save()

    def joblist(self, client):
        return client.get(reverse('order:joblist')).content.decode()

    def detail(self, client, task):
        return client.get(reverse('task:taskdetail', kwargs={'id': task.pk})).content.decode()

    def later(self, client, task, ajax=False):
        extra = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'} if ajax else {}
        return client.post(reverse('task:later', kwargs={'id': task.pk}), **extra)

    def listed(self, html):
        return [name for name in ('A overdue', 'B overdue', 'C today', 'D future') if f'REVTEST {name}' in html]


class SessionLogicTests(ReviewBase):
    def test_no_review_means_nothing_to_go_through(self):
        session = FakeSession()
        self.assertEqual(popup.due_remaining(self.user, session), [])
        self.assertFalse(popup.review_in_progress(self.user, session))
        self.assertFalse(popup.can_postpone(self.user, session, self.a))

    def test_the_due_tasks_left_shrink_as_they_are_put_off(self):
        session = FakeSession()
        popup.start_review(session)
        names = lambda: [t.taskname[8:9] for t in popup.due_remaining(self.user, session)]
        self.assertEqual(names(), ['A', 'B', 'C'])
        self.assertEqual(popup.postpone(self.user, session, self.a), 2)
        self.assertEqual(names(), ['B', 'C'])
        self.assertEqual(popup.postpone(self.user, session, self.a), 2)            # twice counts once
        self.assertTrue(popup.review_in_progress(self.user, session))

    def test_the_review_ends_when_the_last_one_is_put_off(self):
        session = FakeSession()
        popup.start_review(session)
        popup.postpone(self.user, session, self.a)
        popup.postpone(self.user, session, self.b)
        self.assertEqual(popup.postpone(self.user, session, self.c), 0)
        self.assertIsNone(popup._review(session))                                  # nothing is kept any more
        self.assertFalse(popup.review_in_progress(self.user, session))

    def test_a_task_not_due_yet_cannot_be_put_off(self):
        session = FakeSession()
        popup.start_review(session)
        self.assertEqual(popup.postpone(self.user, session, self.future), 3)
        self.assertNotIn(self.future.pk, popup.postponed_ids(session))
        self.assertFalse(popup.can_postpone(self.user, session, self.future))

    def test_only_the_assignee_can_put_a_task_off(self):
        session = FakeSession()
        popup.start_review(session)
        self.assertTrue(popup.can_postpone(self.user, session, self.a))
        self.assertFalse(popup.can_postpone(self.stranger, session, self.a))
        self.assertFalse(popup.can_postpone(self.user, session, self.closed))

    def test_a_task_that_is_done_no_longer_needs_going_through(self):
        session = FakeSession()
        popup.start_review(session)
        Task.objects.filter(pk__in=[self.a.pk, self.b.pk]).update(is_closed=True)
        self.assertEqual([t.pk for t in popup.due_remaining(self.user, session)], [self.c.pk])

    def test_a_review_belongs_to_the_day_it_started(self):
        session = FakeSession()
        popup.start_review(session, today=TODAY - datetime.timedelta(days=1))
        self.assertFalse(popup.review_in_progress(self.user, session, today=TODAY))
        self.assertIsNone(popup._review(session, today=TODAY))


class TheWholeFlowTests(ReviewBase):
    def test_walking_through_every_due_task(self):
        client = self.logged_in()
        self.login_flag(client)
        # 1. right after login: the list, with every due task
        first = self.joblist(client)
        self.assertEqual(self.listed(first), ['A overdue', 'B overdue', 'C today', 'D future'])
        self.assertEqual(first.count(LATER), 3)
        # 2. Open task A: its own page offers Later
        self.assertIn('id="laterButton"', self.detail(client, self.a))
        # 3. Later there: back to the list, which now shows what is left
        response = self.later(client, self.a)
        self.assertRedirects(response, reverse('order:joblist'), fetch_redirect_response=False)
        second = self.joblist(client)
        self.assertEqual(self.listed(second), ['B overdue', 'C today', 'D future'])
        self.assertEqual(second.count(LATER), 2)
        # 4. the same for B, then C: after the last one the list is gone
        self.assertRedirects(self.later(client, self.b), reverse('order:joblist'), fetch_redirect_response=False)
        self.assertEqual(self.listed(self.joblist(client)), ['C today', 'D future'])
        self.assertRedirects(self.later(client, self.c), reverse('order:joblist'), fetch_redirect_response=False)
        done = self.joblist(client)
        self.assertEqual(self.listed(done), [])
        self.assertNotIn('pendingTasksModal" tabindex', done)

    def test_later_never_makes_the_next_visit_look_like_a_new_login(self):
        client = self.logged_in()
        self.login_flag(client)
        self.joblist(client)
        self.later(client, self.a)
        self.assertFalse(client.session.get('show_pending_tasks'))
        # the other due tasks are put off in another window; this one then lands on the job list
        self.later(client, self.b, ajax=True)
        self.later(client, self.c, ajax=True)
        self.assertEqual(self.listed(self.joblist(client)), [])                   # no popup, no restarted review

    def test_the_list_returns_only_while_due_tasks_remain(self):
        client = self.logged_in()
        self.login_flag(client)
        self.joblist(client)
        self.later(client, self.a)
        self.later(client, self.b)
        self.assertEqual(self.listed(self.joblist(client)), ['C today', 'D future'])   # one due task left
        self.later(client, self.c)
        self.assertEqual(self.listed(self.joblist(client)), [])

    def test_the_last_later_says_so(self):
        client = self.logged_in()
        self.login_flag(client)
        self.joblist(client)
        for task in (self.a, self.b):
            self.later(client, task)
        response = self.later(client, self.c)
        messages = [str(m) for m in response.wsgi_request._messages]
        self.assertIn('You have been through all your due tasks.', messages)

    def test_later_in_the_list_and_on_the_task_page_count_together(self):
        client = self.logged_in()
        self.login_flag(client)
        self.joblist(client)
        self.assertEqual(self.later(client, self.a, ajax=True).json(), {'remaining': 2})      # in the pop-up
        self.assertRedirects(self.later(client, self.b), reverse('order:joblist'), fetch_redirect_response=False)
        self.assertEqual(self.listed(self.joblist(client)), ['C today', 'D future'])

    def test_a_task_page_has_no_later_before_or_after(self):
        client = self.logged_in()
        self.assertNotIn('id="laterButton"', self.detail(client, self.a))         # no review yet
        self.login_flag(client)
        self.joblist(client)
        self.assertNotIn('id="laterButton"', self.detail(client, self.future))    # not due
        self.later(client, self.a)
        self.assertNotIn('id="laterButton"', self.detail(client, self.a))         # already put off

    def test_each_login_starts_a_new_review(self):
        client = self.logged_in()
        self.login_flag(client)
        self.joblist(client)
        for task in (self.a, self.b, self.c):
            self.later(client, task)
        again = self.logged_in()
        self.login_flag(again)
        self.assertEqual(self.joblist(again).count(LATER), 3)


class LaterEndpointTests(ReviewBase):
    def started(self):
        client = self.logged_in()
        self.login_flag(client)
        self.joblist(client)
        return client

    def test_only_a_post_works(self):
        client = self.started()
        self.assertEqual(client.get(reverse('task:later', kwargs={'id': self.a.pk})).status_code, 405)

    def test_you_cannot_put_off_somebody_elses_or_a_closed_task(self):
        client = self.started()
        self.assertEqual(self.later(client, self.others).status_code, 404)
        self.assertEqual(self.later(client, self.closed).status_code, 404)

    def test_a_task_not_due_yet_is_refused(self):
        client = self.started()
        self.assertEqual(self.later(client, self.future, ajax=True).status_code, 400)
        response = self.later(client, self.future)
        self.assertRedirects(response, reverse('task:taskdetail', kwargs={'id': self.future.pk}),
                             fetch_redirect_response=False)

    def test_login_is_needed(self):
        response = Client().post(reverse('task:later', kwargs={'id': self.a.pk}))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    def test_it_answers_the_popup_with_how_many_are_left(self):
        client = self.started()
        self.assertEqual(self.later(client, self.a, ajax=True).json(), {'remaining': 2})
        self.assertEqual(self.later(client, self.a, ajax=True).json(), {'remaining': 2})
        self.assertEqual(self.later(client, self.b, ajax=True).json(), {'remaining': 1})
