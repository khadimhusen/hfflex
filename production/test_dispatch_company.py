from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from company.models import Company, default_company, default_company_id
from customer.models import Address, Customer
from production.forms import DispatchForm, DispatchNewForm
from production.models import DispatchRegister


def ensure_default():
    company = default_company()
    if company is None:
        company = Company.objects.create(name='TEST DEFAULT PVT. LTD.', short_name='TD', is_default=True)
    return company


def other_company(**extra):
    values = dict(name='TEST SENDER PVT. LTD.', short_name='TS', gstin='27AAAAA0000A1Z5',
                  address_line1='Gardi', phone='999', email='s@example.com')
    values.update(extra)
    return Company.objects.get_or_create(short_name=values['short_name'], defaults=values)[0]


class DispatchCompanyBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('challanstaff', 'c@example.com', 'x')
        cls.customer = Customer.objects.create(name='TEST CHALLAN BUYER')
        cls.address = Address.objects.create(customer=cls.customer, addname='Plant', add1='Pune')

    def make(self, **extra):
        return DispatchRegister.objects.create(
            customer=self.customer, address=self.address, dispatchdate=timezone.now(),
            createdby=self.user, **extra)


class DispatchModelTests(DispatchCompanyBase):
    def test_a_new_challan_gets_the_default_company(self):
        default = ensure_default()
        self.assertEqual(default_company_id(), default.pk)
        self.assertEqual(self.make().company, default)

    def test_the_sender_can_be_another_company(self):
        ensure_default()
        other = other_company()
        self.assertEqual(self.make(company=other).company, other)

    def test_letterhead_follows_the_sending_company(self):
        ensure_default()
        lh = self.make(company=other_company()).letterhead
        self.assertEqual((lh.name, lh.gstin, lh.phone), ('TEST SENDER PVT. LTD.', '27AAAAA0000A1Z5', '999'))

    def test_a_challan_with_no_company_prints_as_the_default(self):
        default = ensure_default()
        dispatch = self.make()
        DispatchRegister.objects.filter(pk=dispatch.pk).update(company=None)
        dispatch.refresh_from_db()
        self.assertIsNone(dispatch.company)
        self.assertEqual(dispatch.letterhead.name, default.name)

    def test_a_company_with_challans_cannot_be_deleted(self):
        from django.db.models import ProtectedError
        ensure_default()
        other = other_company()
        self.make(company=other)
        with self.assertRaises(ProtectedError):
            other.delete()


class DispatchApiTests(DispatchCompanyBase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.payload = {'customer': self.customer.pk, 'address': self.address.pk,
                        'dispatchdate': '2026-12-01T10:00:00'}
        self.default = ensure_default()

    def post(self, **extra):
        return self.client.post('/api/production/dispatches/', dict(self.payload, **extra), format='json')

    def test_lookup_lists_active_companies_and_marks_the_default(self):
        other = other_company()
        dormant = other_company(name='TEST DORMANT PVT. LTD.', short_name='TZ', gstin='', is_active=False)
        rows = {r['id']: r for r in self.client.get('/api/production/company-lookup/').json()['results']}
        self.assertIn(other.pk, rows)
        self.assertNotIn(dormant.pk, rows)
        self.assertTrue(rows[self.default.pk]['is_default'])

    def test_create_without_a_company_uses_the_default(self):
        response = self.post()
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['company'], self.default.pk)
        self.assertEqual(response.json()['company_name'], self.default.name)

    def test_create_with_a_company(self):
        other = other_company()
        response = self.post(company=other.pk)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['company_name'], other.name)

    def test_an_inactive_company_cannot_be_chosen(self):
        dormant = other_company(name='TEST DORMANT PVT. LTD.', short_name='TZ', gstin='', is_active=False)
        response = self.post(company=dormant.pk)
        self.assertEqual(response.status_code, 400)
        self.assertIn('company', response.json())

    def test_a_challan_keeps_a_company_that_has_since_gone_inactive(self):
        other = other_company()
        dispatch = self.make(company=other)
        Company.objects.filter(pk=other.pk).update(is_active=False)
        response = self.client.patch(f'/api/production/dispatches/{dispatch.pk}/', {'transport': 'X'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['company'], other.pk)

    def test_the_company_can_be_changed(self):
        other = other_company()
        dispatch = self.make()
        response = self.client.patch(f'/api/production/dispatches/{dispatch.pk}/', {'company': other.pk}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        dispatch.refresh_from_db()
        self.assertEqual(dispatch.company, other)

    def test_list_filters_by_company(self):
        other = other_company()
        mine = self.make(company=other)
        self.make(company=self.default)
        rows = self.client.get('/api/production/dispatches/',
                               {'company': other.pk, 'page_size': 100}).json()['results']
        self.assertEqual({r['id'] for r in rows}, {mine.pk})


class DispatchFormTests(DispatchCompanyBase):
    def test_form_offers_active_companies_with_no_blank_choice(self):
        ensure_default()
        other = other_company()
        dormant = other_company(name='TEST DORMANT PVT. LTD.', short_name='TZ', gstin='', is_active=False)
        for form_class in (DispatchNewForm, DispatchForm):
            field = form_class().fields['company']
            offered = set(field.queryset.values_list('pk', flat=True))
            self.assertIn(other.pk, offered)
            self.assertNotIn(dormant.pk, offered)
            self.assertIsNone(field.empty_label)

    def test_editing_a_challan_whose_company_went_inactive_still_lists_it(self):
        ensure_default()
        other = other_company()
        dispatch = self.make(company=other)
        Company.objects.filter(pk=other.pk).update(is_active=False)
        dispatch.refresh_from_db()
        offered = set(DispatchForm(instance=dispatch).fields['company'].queryset.values_list('pk', flat=True))
        self.assertIn(other.pk, offered)

    def test_a_post_without_a_company_is_valid_and_keeps_the_default(self):
        default = ensure_default()
        form = DispatchNewForm({'customer': self.customer.pk, 'address': self.address.pk,
                                'dispatchdate': timezone.now().strftime('%Y-%m-%d %H:%M:%S')})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save(commit=False).company, default)


class ChallanPageTests(DispatchCompanyBase):
    def page(self, dispatch):
        client = Client()
        client.force_login(self.user)
        response = client.get(f'/production/dispatch/detail/{dispatch.pk}/')
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_challan_is_headed_by_the_sending_company(self):
        ensure_default()
        html = self.page(self.make(company=other_company()))
        self.assertIn('TEST SENDER PVT. LTD.', html)
        self.assertIn('Gst:- 27AAAAA0000A1Z5', html)
        self.assertIn('s@example.com', html)
        self.assertNotIn('27AADCH3462K1ZF', html)       # not H F Flex's GSTIN
        self.assertNotIn('hflogo.png', html)             # nor H F Flex's logo

    def test_an_h_f_flex_challan_keeps_its_name_gstin_and_logo(self):
        default = ensure_default()
        if default.gstin != '27AADCH3462K1ZF':
            self.skipTest('the default company here is not H F Flex')
        html = self.page(self.make())
        self.assertIn(default.name, html)
        self.assertIn('Gst:- 27AADCH3462K1ZF', html)
        self.assertIn('hflogo.png', html)
