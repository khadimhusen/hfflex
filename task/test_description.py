"""Task descriptions are written in a rich-text editor and shown as safe HTML."""
import datetime

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase

from task.api_serializers import RecurringTaskSerializer, TaskSerializer
from task.forms import RecurringTaskForm, TaskForm
from task.models import RecurringTask, Task

BAD = '<p>Do <strong>this</strong> now</p><script>alert(1)</script><img src=x onerror="alert(2)"><a href="javascript:alert(3)">x</a>'


class DescriptionBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.boss = User.objects.create_user('descboss', 'a@example.com', 'x')
        cls.worker = User.objects.create_user('descworker', 'b@example.com', 'x')

    def task(self, description, **extra):
        return Task.objects.create(taskname='DESCTEST task', description=description, priority='LOW',
                                   target_date=datetime.datetime.now() + datetime.timedelta(days=5),
                                   task_alloted_to=self.worker, createdby=self.boss, **extra)

    def form_data(self, description, **extra):
        return {'taskname': 'DESCTEST new', 'description': description, 'target_date': '25/12/2030',
                'priority': 'LOW', 'task_alloted_to': self.worker.pk, **extra}


class EditorConfigTests(DescriptionBase):
    def test_the_task_toolbar_is_registered_without_touching_settings_py(self):
        config = settings.CKEDITOR_5_CONFIGS['task_description']
        items = config['toolbar']['items']
        for wanted in ('bold', 'italic', 'underline', 'bulletedList', 'numberedList', 'link', 'undo'):
            self.assertIn(wanted, items)
        for left_out in ('imageUpload', 'mediaEmbed', 'insertTable', 'fontColor'):            # things the cleaner would drop
            self.assertNotIn(left_out, items)

    def test_the_form_fields_use_the_editor(self):
        self.assertIn('ckeditor', TaskForm().fields['description'].widget.__class__.__module__)
        self.assertIn('ckeditor', RecurringTaskForm().fields['description'].widget.__class__.__module__)


class FormTests(DescriptionBase):
    def test_formatting_is_kept_and_danger_is_removed(self):
        form = TaskForm(self.form_data(BAD))
        self.assertTrue(form.is_valid(), form.errors)
        html = form.cleaned_data['description']
        self.assertIn('<strong>this</strong>', html)
        for danger in ('script', 'alert', 'onerror', 'javascript', '<img'):
            self.assertNotIn(danger, html.lower())

    def test_an_emptied_editor_is_refused(self):
        for empty in ('', '<p>&nbsp;</p>', '<p><br></p>', ' <p> </p> '):
            form = TaskForm(self.form_data(empty))
            self.assertFalse(form.is_valid(), repr(empty))
            self.assertIn('description', form.errors)

    def test_plain_text_becomes_lines(self):
        form = TaskForm(self.form_data('Line one\nLine two'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['description'], '<div>Line one</div><div>Line two</div>')

    def test_the_recurring_form_does_the_same(self):
        data = {'taskname': 'DESCTEST recurring', 'description': BAD, 'priority': 'NORMAL', 'task_alloted_to': self.worker.pk,
                'recur_type': 'interval', 'interval_days': 7, 'advance_days': 0, 'is_active': 'on'}
        form = RecurringTaskForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertNotIn('script', form.cleaned_data['description'])
        self.assertIn('<strong>this</strong>', form.cleaned_data['description'])
        data['description'] = '<p>&nbsp;</p>'
        self.assertFalse(RecurringTaskForm(data).is_valid())


class PagesTests(DescriptionBase):
    def client_for(self, user):
        client = Client()
        client.force_login(user)
        return client

    def test_the_add_task_page_loads_the_editor(self):
        html = self.client_for(self.boss).get('/task/addtask/').content.decode()
        self.assertIn('django_ckeditor_5', html)
        self.assertIn('id_description', html)

    def test_adding_a_task_saves_clean_html(self):
        response = self.client_for(self.boss).post('/task/addtask/', self.form_data(BAD))
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None) and response.context['task_form'].errors)
        saved = Task.objects.get(taskname='DESCTEST new')
        self.assertIn('<strong>this</strong>', saved.description)
        self.assertNotIn('script', saved.description)
        self.assertEqual(saved.createdby, self.boss)

    def test_the_task_page_shows_the_formatting(self):
        task = self.task('<p>Call <strong>Rahul</strong></p><ul><li>one</li><li>two</li></ul>')
        html = self.client_for(self.worker).get(f'/task/detail/{task.pk}/').content.decode()
        self.assertIn('<strong>Rahul</strong>', html)
        self.assertIn('<li>one</li>', html)

    def test_something_planted_in_the_database_still_cannot_inject_anything(self):
        task = self.task(BAD)                                   # saved by some other route, not through the form
        html = self.client_for(self.worker).get(f'/task/detail/{task.pk}/').content.decode()
        start = html.index('task-description">')                          # the element, not the CSS rule
        page = html[start:start + 600]
        self.assertIn('<strong>this</strong>', page)
        for danger in ('<script>alert', 'onerror', 'javascript:'):
            self.assertNotIn(danger, html)

    def test_a_description_written_before_the_editor_keeps_its_line_breaks(self):
        task = self.task('First line\nSecond line & more <not a tag>')
        html = self.client_for(self.worker).get(f'/task/detail/{task.pk}/').content.decode()
        self.assertIn('<div>First line</div><div>Second line &amp; more &lt;not a tag&gt;</div>', html)

    def test_the_list_shows_a_plain_snippet_not_tags(self):
        self.task('<p>Call <strong>Rahul</strong> about the <em>quote</em> and then some more words follow here</p>')
        html = self.client_for(self.worker).get('/task/list/').content.decode()    # the default tab: tasks assigned to me
        self.assertIn('<td>Call Rahul about the quote and then so', html)           # plain words, cut at 40 characters
        self.assertNotIn('Rahul</strong>', html.split('<table')[-1])                 # no tags in the table
        self.assertNotIn('<td>&lt;p&gt;', html)


class ApiTests(DescriptionBase):
    def data(self, description):
        return {'taskname': 'DESCTEST api', 'description': description, 'target_date': '2030-12-25T12:00:00',
                'priority': 'LOW', 'task_alloted_to': self.worker.pk}

    def test_it_is_cleaned_on_the_way_in(self):
        serializer = TaskSerializer(data=self.data(BAD))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIn('<strong>this</strong>', serializer.validated_data['description'])
        self.assertNotIn('script', serializer.validated_data['description'])

    def test_blank_is_refused(self):
        for empty in ('', '<p>&nbsp;</p>'):
            serializer = TaskSerializer(data=self.data(empty))
            self.assertFalse(serializer.is_valid())
            self.assertIn('description', serializer.errors)

    def test_plain_text_from_the_old_style_form_becomes_lines(self):
        serializer = TaskSerializer(data=self.data('one\ntwo'))
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['description'], '<div>one</div><div>two</div>')

    def test_it_is_safe_on_the_way_out_even_for_old_or_planted_rows(self):
        self.assertEqual(TaskSerializer(self.task('old text\nline 2')).data['description'], '<div>old text</div><div>line 2</div>')
        shown = TaskSerializer(self.task(BAD)).data['description']
        self.assertIn('<strong>this</strong>', shown)
        for danger in ('script', 'onerror', 'javascript'):
            self.assertNotIn(danger, shown)

    def test_the_recurring_tasks_api_too(self):
        recurring = RecurringTask.objects.create(taskname='DESCTEST rec', description=BAD, priority='LOW',
                                                 task_alloted_to=self.worker, createdby=self.boss, recur_type='interval',
                                                 interval_days=7)
        shown = RecurringTaskSerializer(recurring).data['description']
        self.assertNotIn('script', shown)
        data = {'taskname': 'DESCTEST rec2', 'description': '<p>x</p><script>1</script>', 'priority': 'LOW',
                'task_alloted_to': self.worker.pk, 'recur_type': 'interval', 'interval_days': 7}
        serializer = RecurringTaskSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['description'], '<p>x</p>')
