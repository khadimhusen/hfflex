"""The message box at the bottom of the task page: one compact row, buttons beside the box."""
import datetime

from django.contrib.auth.models import User
from django.test import Client, TestCase

from task.models import Task


class ComposeAreaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.boss = User.objects.create_user('composeboss', 'a@example.com', 'x')
        cls.worker = User.objects.create_user('composeworker', 'b@example.com', 'x')

    def page(self, **extra):
        task = Task.objects.create(taskname='COMPOSETEST task', description='x', priority='LOW',
                                   target_date=datetime.datetime.now() + datetime.timedelta(days=5),
                                   task_alloted_to=self.worker, createdby=self.boss, **extra)
        client = Client()
        client.force_login(self.worker)
        return client.get(f'/task/detail/{task.pk}/').content.decode()

    def test_the_box_and_all_three_buttons_share_one_row(self):
        html = self.page()
        start = html.index('<div class="compose-row">')
        end = html.index('id="msg-error"')
        row = html[start:end]
        for part in ('id="id_msg_text"', 'for="id_msg_image"', 'for="id_msg_file"', 'id="send-btn"'):
            self.assertIn(part, row, part)
        self.assertLess(row.index('id="id_msg_text"'), row.index('for="id_msg_image"'))     # the box comes first,
        self.assertLess(row.index('for="id_msg_file"'), row.index('id="send-btn"'))         # Send comes last

    def test_the_message_box_is_above_the_message_list(self):
        html = self.page()
        self.assertLess(html.index('id="ajax-msg-form"'), html.index('id="chat-box"'))
        self.assertLess(html.index('id="msg-count"'), html.index('id="ajax-msg-form"'))     # under the Messages header

    def test_request_to_close_sits_beside_the_task_list_button(self):
        html = self.page()                                   # the worker, who is allowed to ask for it to be closed
        top = html[html.index('class="mb-3 top-actions"'):html.index('task-header-card shadow-sm')]
        self.assertIn('Task List', top)
        self.assertIn('Request to Close', top)
        self.assertLess(top.index('Task List'), top.index('Request to Close'))
        card = html[html.index('task-header-card shadow-sm'):html.index('id="ajax-msg-form"')]
        self.assertNotIn('Request to Close', card)

    def test_the_old_stacked_layout_is_gone(self):
        html = self.page()
        self.assertNotIn('custom-file-label', html)
        self.assertNotIn('class="form-row"', html[html.index('ajax-msg-form'):html.index('id="msg-error"')])

    def test_the_file_fields_keep_their_names_so_sending_still_works(self):
        html = self.page()
        self.assertIn('name="msg_text"', html)
        self.assertIn('name="msg_image" accept="image/*"', html)
        self.assertIn('name="msg_file"', html)
        self.assertIn("document.getElementById('id_msg_image').files[0]", html)            # the script reads them by id

    def test_the_site_wide_submit_guard_is_kept_off_this_ajax_form(self):
        # that guard (templates/home.html) re-labels the Send button 4s later from the spinner it saw: blank
        html = self.page()
        handler = html[html.index("ajaxForm.addEventListener('submit'"):]
        self.assertIn('e.stopImmediatePropagation()', handler[:600])

    def test_a_closed_task_has_no_message_box(self):
        self.assertNotIn('compose-row"', self.page(is_closed=True).split('</style>', 1)[1])
