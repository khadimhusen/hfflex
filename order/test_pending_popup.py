"""The pending-tasks popup shown right after login (order/templates/job/joblist.html)."""
import datetime

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from task.models import Task
from task.popup import UPCOMING_SHOWN, login_popup_tasks

LATER = 'class="btn btn-outline-secondary btn-sm later-btn"'
TODAY = datetime.date.today()


def at(days, hour=12):
    return datetime.datetime.combine(TODAY + datetime.timedelta(days=days), datetime.time(hour, 0))


class PopupBase(TestCase):
    @classmethod
    def make_user(cls, name):
        return User.objects.create_user(name, f'{name}@example.com', 'x')

    @classmethod
    def task(cls, user, name, when, **extra):
        return Task.objects.create(taskname=f'POPTEST {name}', description='x', target_date=when, task_alloted_to=user,
                                   createdby=cls.boss, **extra)

    @classmethod
    def setUpTestData(cls):
        cls.boss = cls.make_user('popboss')
        cls.user = cls.make_user('poptester')
        cls.overdue = cls.task(cls.user, 'overdue', at(-1))
        cls.today = cls.task(cls.user, 'today', datetime.datetime.combine(TODAY, datetime.time(23, 59)))
        cls.tomorrow = cls.task(cls.user, 'tomorrow', at(1))
        cls.later_on = cls.task(cls.user, 'next week', at(5))
        cls.task(cls.user, 'closed', at(-3), is_closed=True)
        cls.task(cls.boss, 'somebody elses', at(-2))

    def joblist(self, user, flag=True):
        client = Client()
        client.force_login(user)
        if flag:
            session = client.session
            session['show_pending_tasks'] = True
            session.save()
        return client.get(reverse('order:joblist')).content.decode()


class WhichTasksAreListedTests(PopupBase):
    def names(self, user=None):
        return [t.taskname.replace('POPTEST ', '') for t in login_popup_tasks(user or self.user, TODAY)]

    def test_due_tasks_first_then_the_upcoming_ones(self):
        self.assertEqual(self.names(), ['overdue', 'today', 'tomorrow', 'next week'])

    def test_a_task_due_late_today_counts_as_due(self):
        self.assertIn('today', self.names())
        late = Task.objects.get(pk=self.today.pk)
        self.assertEqual(late.target_date.time(), datetime.time(23, 59))

    def test_closed_tasks_and_other_peoples_tasks_are_left_out(self):
        self.assertNotIn('closed', self.names())
        self.assertNotIn('somebody elses', self.names())

    def test_every_due_task_is_listed_however_many_there_are(self):
        for number in range(12):
            self.task(self.user, f'old {number}', at(-10 + number % 3))
        due = [t for t in login_popup_tasks(self.user, TODAY) if t.target_date <= datetime.datetime.combine(TODAY, datetime.time.max)]
        self.assertEqual(len(due), 14)                                    # 12 + overdue + today

    def test_only_a_few_upcoming_tasks_are_listed(self):
        for number in range(15):
            self.task(self.user, f'future {number}', at(10 + number))
        upcoming = [t for t in login_popup_tasks(self.user, TODAY) if t.target_date > datetime.datetime.combine(TODAY, datetime.time.max)]
        self.assertEqual(len(upcoming), UPCOMING_SHOWN)
        self.assertEqual(upcoming[0].taskname, 'POPTEST tomorrow')        # the soonest ones


class PopupPageTests(PopupBase):
    def test_later_only_on_tasks_due_today_or_earlier(self):
        html = self.joblist(self.user)
        self.assertEqual(html.count(LATER), 2)                            # overdue + today, not tomorrow / next week
        rows = html.split('<tr>')
        later_in = lambda name: LATER in next(r for r in rows if f'POPTEST {name}' in r)
        self.assertTrue(later_in('overdue') and later_in('today'))
        self.assertFalse(later_in('tomorrow') or later_in('next week'))

    def test_due_tasks_are_labelled(self):
        html = self.joblist(self.user)
        self.assertEqual(html.count('class="due-label text-danger">Overdue<'), 1)
        self.assertEqual(html.count('class="due-label text-warning">Due today<'), 1)

    def test_there_is_no_view_all_my_tasks_way_round_it(self):
        html = self.joblist(self.user)
        start = html.index('id="pendingTasksModal"')
        popup = html[start:html.index('Dismiss</button>', start)]          # the login popup only
        self.assertNotIn('View All', popup)
        self.assertNotIn('tab=assigned', popup)
        self.assertNotIn('tasklist', popup)

    def test_it_cannot_be_closed_until_every_due_later_is_clicked(self):
        html = self.joblist(self.user)
        self.assertEqual(html.count('pending-close d-none'), 2)           # the X and Dismiss start hidden
        self.assertIn("backdrop: 'static'", html)
        self.assertIn('keyboard: false', html)
        self.assertIn('id="pendingLaterHint" class="d-none"', html)       # the script shows it when something is due

    def test_with_nothing_due_it_is_an_ordinary_popup(self):
        calm = self.make_user('popcalm')
        self.task(calm, 'far off', at(4))
        html = self.joblist(calm)
        self.assertIn('POPTEST far off', html)
        self.assertNotIn(LATER, html)                                     # no Later buttons, so nothing to lock on
        self.assertIn("$modal.find('.pending-close').removeClass('d-none')", html)

    def test_no_popup_without_the_login_flag_or_without_tasks(self):
        self.assertNotIn('later-btn"', self.joblist(self.user, flag=False))
        self.assertNotIn('pendingTasksModal" tabindex', self.joblist(self.make_user('popnone')))

    def test_the_popup_comes_back_while_a_due_task_is_not_put_off(self):
        client = Client()
        client.force_login(self.user)
        session = client.session
        session['show_pending_tasks'] = True
        session.save()
        first = client.get(reverse('order:joblist')).content.decode()
        second = client.get(reverse('order:joblist')).content.decode()       # the flag is gone, the review is not
        self.assertEqual((first.count(LATER), second.count(LATER)), (2, 2))

    def test_an_ordinary_popup_shows_once(self):
        calm = self.make_user('popcalm2')
        self.task(calm, 'far off', at(4))
        client = Client()
        client.force_login(calm)
        session = client.session
        session['show_pending_tasks'] = True
        session.save()
        self.assertIn('POPTEST far off', client.get(reverse('order:joblist')).content.decode())
        self.assertNotIn('POPTEST far off', client.get(reverse('order:joblist')).content.decode())

    def test_each_later_button_knows_its_task(self):
        html = self.joblist(self.user)
        self.assertIn(f'data-task-id="{self.overdue.pk}"', html)
        self.assertIn(f'data-task-id="{self.today.pk}"', html)
        self.assertNotIn(f'data-task-id="{self.tomorrow.pk}"', html)
        self.assertIn('/task/later/', html)                                   # where the buttons save to
