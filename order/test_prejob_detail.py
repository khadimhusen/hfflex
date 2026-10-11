import datetime

from django.contrib.auth.models import User
from django.test import Client, TestCase
from rest_framework.test import APIClient

from material.models import Unit
from preorder.models import JobName, PreOrder


class PrejobDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('prejobstaff', 'p@example.com', 'x')
        cls.unit = Unit.objects.get_or_create(unit='TESTKG')[0]
        cls.preorder = PreOrder.objects.create(
            customer='TEST PREORDER CUSTOMER', address='Pune', gst='27AAAAA0000A1Z5',
            contact_number='9876543210', schedule=datetime.date(2026, 12, 5),
            final_submition=True, createdby=cls.user)
        cls.job = JobName.objects.create(
            preorder=cls.preorder, jobname='TEST POUCH', qty=500, unit=cls.unit, new_cylinder=True,
            new_cyl_qty=4, cyl_invoice='INV-7', cyl_cost=1200, design_charges=300, rate=12.5,
            remark='Customer wants matte finish, deliver in two lots.', createdby=cls.user)

    def test_lookup_carries_the_preorders_remark_and_details(self):
        client = APIClient()
        client.force_authenticate(self.user)
        rows = client.get('/api/order/prejob-lookup/', {'page_size': 500}).json()['results']
        row = next(r for r in rows if r['id'] == self.job.pk)
        self.assertEqual(row['remark'], 'Customer wants matte finish, deliver in two lots.')
        self.assertEqual(row['preorder'], self.preorder.pk)
        self.assertEqual(row['preorder_schedule'], '2026-12-05')
        self.assertEqual(row['preorder_contact'], '9876543210')
        self.assertEqual(row['cyl_invoice'], 'INV-7')
        self.assertEqual((row['cyl_cost'], row['design_charges']), ('1200.00', '300.00'))
        self.assertEqual(row['new_cyl_qty'], 4)
        self.assertIsNone(row['preimg_thumbnail_url'])
        self.assertFalse(row['preimg'])

    def test_old_app_endpoint_returns_rows_and_remark(self):
        client = Client()
        client.force_login(self.user)
        data = client.get('/order/ajax/prejob-detail/', {'prejob': self.job.pk}).json()
        rows = dict(data['rows'])
        self.assertEqual(rows['Preorder'], f'#{self.preorder.pk} - TEST PREORDER CUSTOMER')
        self.assertEqual(rows['Schedule'], '05/12/2026')
        self.assertEqual(rows['New cylinder qty'], '4')
        self.assertEqual(data['remark'], 'Customer wants matte finish, deliver in two lots.')
        self.assertEqual((data['image'], data['file']), ('', ''))

    def test_old_app_endpoint_for_nothing_is_empty(self):
        client = Client()
        client.force_login(self.user)
        self.assertEqual(client.get('/order/ajax/prejob-detail/', {'prejob': ''}).json(), {})
        self.assertEqual(client.get('/order/ajax/prejob-detail/', {'prejob': 999999999}).json(), {})

    def test_old_app_endpoint_needs_a_login(self):
        response = Client().get('/order/ajax/prejob-detail/', {'prejob': self.job.pk})
        self.assertEqual(response.status_code, 302)
