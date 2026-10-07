from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from company.models import Company, default_company, default_company_id
from customer.models import Customer
from purchase.forms import PoForm
from purchase.models import Po


def ensure_default():
    """The default company -- the one already there, or a new one in an empty database."""
    company = default_company()
    if company is None:
        company = Company.objects.create(name='TEST DEFAULT PVT. LTD.', short_name='TD', is_default=True)
    return company


def other_company(**extra):
    values = dict(name='TEST OTHER PVT. LTD.', short_name='TO')
    values.update(extra)
    return Company.objects.get_or_create(short_name=values['short_name'], defaults=values)[0]


def make_po(supplier, **extra):
    # delivery_at / ship_to have hard-coded defaults (a pk, a customer name);
    # give them values so the test doesn't depend on those rows existing.
    # Po.save() logs an ExpectedDate row whose createdby is required.
    extra.setdefault('createdby', User.objects.get(username='buyerstaff'))
    extra.setdefault('delivery_at', None)
    return Po.objects.create(supplier=supplier, delivery_date=timezone.now(), **extra)


class BuyerTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Po.ship_to defaults to this exact customer name.
        Customer.objects.get_or_create(name='H F FLEX PRIVATE LIMITED', defaults=dict(gst='27AADCH3462K1ZF'))
        cls.supplier = Customer.objects.get_or_create(
            name='TEST SUPPLIER', defaults=dict(is_supplier=True, active=True))[0]
        cls.staff = User.objects.create_superuser('buyerstaff', 'b@example.com', 'x')


class PoBuyerModelTests(BuyerTestBase):
    def test_a_new_po_gets_the_default_company(self):
        default = ensure_default()
        self.assertEqual(default_company_id(), default.pk)
        self.assertEqual(make_po(self.supplier).buyer, default)

    def test_the_buyer_can_be_another_company(self):
        ensure_default()
        other = other_company()
        self.assertEqual(make_po(self.supplier, buyer=other).buyer, other)

    def test_letterhead_follows_the_buyer(self):
        ensure_default()
        other = other_company(name='TEST OTHER PVT. LTD.', phone='999')
        lh = make_po(self.supplier, buyer=other).letterhead
        self.assertEqual((lh.name, lh.phone), ('TEST OTHER PVT. LTD.', '999'))

    def test_a_po_with_no_buyer_prints_as_the_default_company(self):
        default = ensure_default()
        po = make_po(self.supplier)
        Po.objects.filter(pk=po.pk).update(buyer=None)
        po.refresh_from_db()
        self.assertIsNone(po.buyer)
        self.assertEqual(po.letterhead.name, default.name)

    def test_a_company_with_orders_cannot_be_deleted(self):
        ensure_default()
        other = other_company()
        make_po(self.supplier, buyer=other)
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            other.delete()


class BackfillCommandTests(BuyerTestBase):
    def run_command(self, *args):
        out = StringIO()
        call_command('backfill_po_buyer', *args, stdout=out)
        return out.getvalue()

    def test_fills_only_orders_without_a_buyer(self):
        default = ensure_default()
        other = other_company()
        missing = make_po(self.supplier)
        Po.objects.filter(pk=missing.pk).update(buyer=None)
        owned = make_po(self.supplier, buyer=other)
        self.run_command()
        missing.refresh_from_db()
        owned.refresh_from_db()
        self.assertEqual(missing.buyer, default)
        self.assertEqual(owned.buyer, other)  # never touched

    def test_dry_run_changes_nothing(self):
        ensure_default()
        missing = make_po(self.supplier)
        Po.objects.filter(pk=missing.pk).update(buyer=None)
        self.assertIn('would set', self.run_command('--dry-run'))
        missing.refresh_from_db()
        self.assertIsNone(missing.buyer)

    def test_company_option_picks_another_company(self):
        ensure_default()
        other = other_company()
        missing = make_po(self.supplier)
        Po.objects.filter(pk=missing.pk).update(buyer=None)
        self.run_command('--company', other.short_name)
        missing.refresh_from_db()
        self.assertEqual(missing.buyer, other)

    def test_unknown_company_is_an_error(self):
        ensure_default()
        with self.assertRaises(CommandError):
            self.run_command('--company', 'NOPE')


class PoBuyerApiTests(BuyerTestBase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        self.payload = {'supplier': self.supplier.id, 'delivery_date': '2026-12-01T10:00:00'}

    def test_lookup_lists_only_active_companies_and_marks_the_default(self):
        default = ensure_default()
        other = other_company()
        inactive = other_company(name='TEST DORMANT PVT. LTD.', short_name='TZ', is_active=False)
        rows = self.client.get('/api/purchase/buyer-lookup/').json()['results']
        by_id = {row['id']: row for row in rows}
        self.assertIn(other.pk, by_id)
        self.assertNotIn(inactive.pk, by_id)
        self.assertTrue(by_id[default.pk]['is_default'])
        self.assertFalse(by_id[other.pk]['is_default'])

    def test_create_without_a_buyer_uses_the_default(self):
        default = ensure_default()
        response = self.client.post('/api/purchase/purchase-orders/', self.payload, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['buyer'], default.pk)
        self.assertEqual(response.json()['buyer_name'], default.name)

    def test_create_with_a_buyer(self):
        ensure_default()
        other = other_company()
        response = self.client.post('/api/purchase/purchase-orders/', dict(self.payload, buyer=other.pk), format='json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['buyer_name'], other.name)

    def test_an_inactive_company_cannot_be_chosen(self):
        ensure_default()
        dormant = other_company(name='TEST DORMANT PVT. LTD.', short_name='TZ', is_active=False)
        response = self.client.post('/api/purchase/purchase-orders/', dict(self.payload, buyer=dormant.pk), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('buyer', response.json())

    def test_an_order_keeps_a_buyer_that_has_since_gone_inactive(self):
        ensure_default()
        other = other_company()
        po = make_po(self.supplier, buyer=other)
        Company.objects.filter(pk=other.pk).update(is_active=False)
        response = self.client.patch(f'/api/purchase/purchase-orders/{po.pk}/', {'remark': 'edited'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['buyer'], other.pk)

    def test_the_buyer_can_be_changed(self):
        ensure_default()
        other = other_company()
        po = make_po(self.supplier)
        response = self.client.patch(f'/api/purchase/purchase-orders/{po.pk}/', {'buyer': other.pk}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        po.refresh_from_db()
        self.assertEqual(po.buyer, other)

    def test_list_filters_by_buyer(self):
        default = ensure_default()
        other = other_company()
        mine = make_po(self.supplier, buyer=other)
        make_po(self.supplier, buyer=default)
        rows = self.client.get('/api/purchase/purchase-orders/', {'buyer': other.pk, 'page_size': 100}).json()['results']
        self.assertEqual({row['id'] for row in rows}, {mine.pk})


class PoFormBuyerTests(BuyerTestBase):
    def test_new_form_offers_only_active_companies_with_no_blank_choice(self):
        ensure_default()
        other = other_company()
        dormant = other_company(name='TEST DORMANT PVT. LTD.', short_name='TZ', is_active=False)
        field = PoForm().fields['buyer']
        offered = set(field.queryset.values_list('pk', flat=True))
        self.assertIn(other.pk, offered)
        self.assertNotIn(dormant.pk, offered)
        self.assertIsNone(field.empty_label)

    def test_editing_an_order_whose_buyer_went_inactive_still_lists_that_buyer(self):
        ensure_default()
        other = other_company()
        po = make_po(self.supplier, buyer=other)
        Company.objects.filter(pk=other.pk).update(is_active=False)
        po.refresh_from_db()
        offered = set(PoForm(instance=po).fields['buyer'].queryset.values_list('pk', flat=True))
        self.assertIn(other.pk, offered)

    def test_omitting_the_buyer_from_a_post_keeps_the_orders_buyer(self):
        # A page loaded before this field existed posts no buyer at all.
        default = ensure_default()
        other = other_company()
        po = make_po(self.supplier, buyer=other)
        form = PoForm({
            'supplier': self.supplier.pk, 'delivery_date': timezone.now().strftime('%d/%m/%Y %H:%M'),
            'payment_terms': 30, 'tax1': 9, 'tax2': 9, 'status': 'Pending', 'remark': '-',
        }, instance=po)
        form.is_valid()
        self.assertNotIn('buyer', form.errors)
        self.assertEqual(form.cleaned_data.get('buyer') or po.buyer, other)
        self.assertNotEqual(po.buyer, default)
