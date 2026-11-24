"""The Task page link in the old app's sidebar."""
from django.contrib.auth.models import User
from django.test import Client, TestCase

from employee.models import Department


class SidebarTaskLinkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.plain = User.objects.create_user('sidebarplain', 'a@example.com', 'x')
        cls.crm = User.objects.create_user('sidebarcrm', 'b@example.com', 'x')
        Department.objects.get_or_create(department_name='crm_user')[0].user.add(cls.crm)

    def page(self, user):
        client = Client()
        client.force_login(user)
        return client.get('/order/joblist/').content.decode()

    def test_everybody_gets_a_task_link_in_the_sidebar(self):
        html = self.page(self.plain)
        sidebar = html[html.index('class="sidebar'):]
        self.assertIn('id="sidebarTaskLink"', sidebar)
        self.assertIn('href="/task/list/"', sidebar)

    def test_it_sits_above_the_crm_link(self):
        html = self.page(self.crm)
        sidebar = html[html.index('class="sidebar'):]
        self.assertIn('/crm/', sidebar)                                              # this user does see the CRM link
        self.assertLess(sidebar.index('id="sidebarTaskLink"'), sidebar.index('>RM</a>'))

    def test_a_user_without_the_crm_department_still_sees_the_task_link(self):
        sidebar = self.page(self.plain)
        sidebar = sidebar[sidebar.index('class="sidebar'):]
        self.assertNotIn('>RM</a>', sidebar)
        self.assertIn('id="sidebarTaskLink"', sidebar)
