"""A new task cannot be given a target date before today."""
import datetime

from django.contrib.auth.models import User
from django.test import Client, TestCase

from task.api_serializers import TaskSerializer
from task.forms import TaskForm
from task.models import Task

TODAY = datetime.date.today()


def day(offset):
    return TODAY + datetime.timedelta(days=offset)


class NewTaskDateBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.boss = User.objects.create_user('dateboss', 'a@example.com', 'x')
        cls.worker = User.objects.create_user('dateworker', 'b@example.com', 'x')

    def form_data(self, target):
        return {'taskname': 'DATETEST new', 'description': '<p>Do it</p>', 'target_date': target.strftime('%d/%m/%Y'),
                'priority': 'LOW', 'task_alloted_to': self.worker.pk}


class FormTests(NewTaskDateBase):
    def test_a_date_before_today_is_refused(self):
        for offset in (-1, -7, -400):
            form = TaskForm(self.form_data(day(offset)))
            self.assertFalse(form.is_valid(), offset)
            self.assertEqual(form.errors['target_date'], ['The target date cannot be before today.'])

    def test_today_and_later_are_fine(self):
        for offset in (0, 1, 30):
            form = TaskForm(self.form_data(day(offset)))
            self.assertTrue(form.is_valid(), (offset, form.errors))

    def test_editing_an_existing_task_is_not_blocked_by_its_old_date(self):
        old = Task.objects.create(taskname='DATETEST old', description='x', priority='LOW', target_date=datetime.datetime.combine(day(-10), datetime.time(12, 0)),
                                  task_alloted_to=self.worker, createdby=self.boss)
        form = TaskForm(self.form_data(day(-10)), instance=old)
        self.assertTrue(form.is_valid(), form.errors)


class PageTests(NewTaskDateBase):
    def logged_in(self):
        client = Client()
        client.force_login(self.boss)
        return client

    def test_the_page_greys_out_earlier_days(self):
        html = self.logged_in().get('/task/addtask/').content.decode()
        self.assertIn('minDate: 0', html)

    def test_posting_a_past_date_creates_nothing_and_says_why(self):
        response = self.logged_in().post('/task/addtask/', self.form_data(day(-1)))
        self.assertEqual(response.status_code, 200)                                  # back to the form
        self.assertIn('cannot be before today', response.content.decode())
        self.assertFalse(Task.objects.filter(taskname='DATETEST new').exists())

    def test_posting_today_works(self):
        response = self.logged_in().post('/task/addtask/', self.form_data(TODAY))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Task.objects.filter(taskname='DATETEST new', target_date__date=TODAY).exists())


class ApiTests(NewTaskDateBase):
    def data(self, when):
        return {'taskname': 'DATETEST api', 'description': '<p>x</p>', 'target_date': when.isoformat(),
                'priority': 'LOW', 'task_alloted_to': self.worker.pk}

    def test_creating_with_a_date_before_today_is_refused(self):
        yesterday_late = datetime.datetime.combine(day(-1), datetime.time(23, 59))
        serializer = TaskSerializer(data=self.data(yesterday_late))
        self.assertFalse(serializer.is_valid())
        self.assertIn('target_date', serializer.errors)

    def test_the_start_of_today_and_later_are_fine(self):
        for when in (datetime.datetime.combine(TODAY, datetime.time.min), datetime.datetime.combine(day(5), datetime.time(9, 0))):
            serializer = TaskSerializer(data=self.data(when))
            self.assertTrue(serializer.is_valid(), (when, serializer.errors))

    def test_updating_an_existing_task_is_not_stopped_by_the_creation_rule(self):
        task = Task.objects.create(taskname='DATETEST old', description='x', priority='LOW',
                                   target_date=datetime.datetime.combine(day(-10), datetime.time(12, 0)),
                                   task_alloted_to=self.worker, createdby=self.boss)
        serializer = TaskSerializer(task, data={'taskname': 'DATETEST renamed'}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
