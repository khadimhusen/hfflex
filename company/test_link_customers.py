from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from customer.models import Address, Customer

from .defaults import HF_FLEX
from .models import Company, LEGACY_CUSTOMER_NAME, company_for_customer


def run(*args):
    out = StringIO()
    call_command('link_company_customers', *args, stdout=out)
    return out.getvalue()


def make_company(**extra):
    values = dict(name='TEST LINK PVT. LTD.', short_name='TK', gstin='27AAAAA0000A1Z5',
                  address_line1='Gardi', address_line2='Vita', phone='8552827683', email='t@example.com')
    values.update(extra)
    return Company.objects.create(**values)


class LinkCompanyCustomersTests(TestCase):
    def test_links_an_existing_customer_found_by_gstin(self):
        customer = Customer.objects.create(name='SOMETHING ELSE', gst='27AAAAA0000A1Z5')
        company = make_company()
        run()
        company.refresh_from_db()
        self.assertEqual(company.customer, customer)

    def test_without_create_it_makes_nothing(self):
        company = make_company()
        count = Customer.objects.count()
        self.assertIn('no matching customer', run())
        company.refresh_from_db()
        self.assertIsNone(company.customer)
        self.assertEqual(Customer.objects.count(), count)

    def test_create_makes_the_customer_with_the_companys_address(self):
        company = make_company()
        run('--create')
        company.refresh_from_db()
        self.assertEqual(company.customer.name, 'TEST LINK PVT. LTD.')
        self.assertEqual(company.customer.gst, '27AAAAA0000A1Z5')
        address = Address.objects.get(customer=company.customer)
        self.assertEqual((address.add1, address.add2), ('Gardi', 'Vita'))
        self.assertEqual(list(company.delivery_addresses()), [address])

    def test_dry_run_changes_nothing(self):
        company = make_company()
        count = Customer.objects.count()
        self.assertIn('would create', run('--create', '--dry-run'))
        company.refresh_from_db()
        self.assertIsNone(company.customer)
        self.assertEqual(Customer.objects.count(), count)

    def test_a_company_already_linked_is_left_alone(self):
        mine = Customer.objects.create(name='MY OWN RECORD')
        company = make_company(customer=mine)
        Customer.objects.create(name='TEST LINK PVT. LTD.')
        run('--create')
        company.refresh_from_db()
        self.assertEqual(company.customer, mine)

    def test_running_twice_creates_it_once(self):
        make_company()
        run('--create')
        count = Customer.objects.count()
        run('--create')
        self.assertEqual(Customer.objects.count(), count)


class ReceivingCustomerTests(TestCase):
    def test_h_f_flex_finds_its_legacy_record_by_name_even_unlinked(self):
        legacy = Customer.objects.get_or_create(name=LEGACY_CUSTOMER_NAME)[0]
        flex = (Company.objects.filter(gstin=HF_FLEX['gstin']).first()
                or make_company(name=HF_FLEX['name'], short_name='HFX', gstin=HF_FLEX['gstin']))
        Company.objects.filter(pk=flex.pk).update(customer=None)
        flex.refresh_from_db()
        self.assertEqual(flex.receiving_customer, legacy)
        self.assertEqual(company_for_customer(legacy), flex)

    def test_another_company_without_a_link_has_none(self):
        Customer.objects.get_or_create(name=LEGACY_CUSTOMER_NAME)
        self.assertIsNone(make_company().receiving_customer)
        self.assertEqual(list(make_company(name='X PVT. LTD.', short_name='XX', gstin='').delivery_addresses()), [])

    def test_company_for_customer_ignores_outside_parties(self):
        outside = Customer.objects.create(name='AN OUTSIDE PARTY')
        self.assertIsNone(company_for_customer(outside))
        self.assertIsNone(company_for_customer(None))


class AdminSaveLinksCustomerTests(TestCase):
    def save_in_admin(self, company, **extra):
        from unittest import mock
        from django.contrib import admin
        from django.contrib.auth.models import User
        user = User.objects.create_superuser('linkadmin', 'l@example.com', 'x')
        request = mock.Mock(user=user)
        admin.site._registry[Company].save_model(request, company, form=None, change=False)

    def test_a_company_saved_in_the_admin_gets_a_customer_with_its_address(self):
        company = Company(name='TEST ADMIN PVT. LTD.', short_name='TA', gstin='', address_line1='Vita')
        self.save_in_admin(company)
        company.refresh_from_db()
        self.assertEqual(company.customer.name, 'TEST ADMIN PVT. LTD.')
        self.assertEqual([a.add1 for a in company.delivery_addresses()], ['Vita'])

    def test_a_customer_picked_in_the_admin_is_kept(self):
        mine = Customer.objects.create(name='PICKED BY HAND')
        company = Company(name='TEST ADMIN PVT. LTD.', short_name='TA', customer=mine)
        self.save_in_admin(company)
        company.refresh_from_db()
        self.assertEqual(company.customer, mine)
        self.assertFalse(Customer.objects.filter(name='TEST ADMIN PVT. LTD.').exists())
