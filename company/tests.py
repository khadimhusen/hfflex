from io import StringIO

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Company


def make(short_name, **extra):
    return Company.objects.create(name=f'{short_name} PVT. LTD.', short_name=short_name, **extra)


class CompanyModelTests(TestCase):
    def test_str_is_the_name(self):
        self.assertEqual(str(make('AA')), 'AA PVT. LTD.')

    def test_only_one_default_company(self):
        make('AA', is_default=True)
        with self.assertRaises(IntegrityError), transaction.atomic():
            make('BB', is_default=True)

    def test_any_number_of_non_default_companies(self):
        make('AA', is_default=True)
        make('BB')
        make('CC')
        self.assertEqual(Company.objects.filter(is_default=False).count(), 2)

    def test_default_has_to_be_active(self):
        company = Company(name='X', short_name='X', is_default=True, is_active=False)
        with self.assertRaises(ValidationError):
            company.full_clean()

    def test_name_and_short_name_are_unique(self):
        make('AA')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Company.objects.create(name='AA PVT. LTD.', short_name='ZZ')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Company.objects.create(name='Other', short_name='AA')

    def test_gstin_is_tidied_before_the_format_check(self):
        company = Company(name='X', short_name='X', gstin=' 27aadch3462k1zf ')
        company.full_clean()  # would raise if the check ran on the raw value
        self.assertEqual(company.gstin, '27AADCH3462K1ZF')

    def test_gstin_wrong_format_is_refused(self):
        for bad in ['27AADCH3462K1Z', '27AADCH3462K1XF', 'ABCDEFGHIJKLMNO', '27AADCH34621KZF']:
            with self.assertRaises(ValidationError, msg=bad):
                Company(name='X', short_name='X', gstin=bad).full_clean()

    def test_gstin_is_optional(self):
        Company(name='X', short_name='X').full_clean()

    def test_gstin_is_upper_cased_on_plain_save(self):
        company = make('AA', gstin='27aadch3462k1zf')
        company.refresh_from_db()
        self.assertEqual(company.gstin, '27AADCH3462K1ZF')

    def test_state_code(self):
        self.assertEqual(make('AA', gstin='27AADCH3462K1ZF').state_code, '27')
        self.assertEqual(make('BB').state_code, '')


class SeedCommandTests(TestCase):
    def run_seed(self):
        out = StringIO()
        call_command('seed_companies', stdout=out)
        return out.getvalue()

    def test_creates_h_f_flex_as_the_default(self):
        self.run_seed()
        company = Company.objects.get(short_name='HF')
        self.assertEqual(company.name, 'H F FLEX PVT. LTD.')
        self.assertEqual(company.gstin, '27AADCH3462K1ZF')
        self.assertTrue(company.is_default and company.is_active)

    def test_rerun_changes_nothing(self):
        self.run_seed()
        Company.objects.filter(short_name='HF').update(phone='edited in admin')
        self.assertIn('already exists', self.run_seed())
        self.assertEqual(Company.objects.count(), 1)
        self.assertEqual(Company.objects.get().phone, 'edited in admin')


class CompanyAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('boss', 'boss@example.com', 'x')

    def setUp(self):
        self.client.force_login(self.admin)

    def test_list_and_add_pages_load(self):
        make('AA')
        self.assertEqual(self.client.get('/admin/company/company/').status_code, 200)
        self.assertEqual(self.client.get('/admin/company/company/add/').status_code, 200)

    def test_adding_records_who_created_it(self):
        response = self.client.post('/admin/company/company/add/', {
            'name': 'H F PRINTPACK PVT. LTD.', 'short_name': 'HP', 'gstin': '27aadch3462k1zf',
            'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        company = Company.objects.get(short_name='HP')
        self.assertEqual(company.createdby, self.admin)
        self.assertEqual(company.editedby, self.admin)
        self.assertEqual(company.gstin, '27AADCH3462K1ZF')
