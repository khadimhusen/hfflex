import datetime
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from customer.models import Customer
from itemmaster.forms import CylinderMovementForm
from itemmaster.locations import cylinder_locations_for
from itemmaster.models import CylinderMovement, ItemMaster


def place(name, **extra):
    values = dict(is_customer=False, is_cylinder_location=True)
    values.update(extra)
    return Customer.objects.get_or_create(name=name, defaults=values)[0]


class CylinderLocationBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('cylstaff', 'c@example.com', 'x')
        cls.customer = Customer.objects.create(name='TEST CYL CUSTOMER')
        cls.other_customer = Customer.objects.create(name='TEST OTHER CUSTOMER')
        cls.godown = place('TEST GODOWN A')
        cls.production = place('TEST PRODUCTION AREA')
        cls.item = ItemMaster.objects.create(itemname='TEST POUCH', itemcustomer=cls.customer)


class LocationHelperTests(CylinderLocationBase):
    def names(self, item=None):
        return set(cylinder_locations_for(item or self.item).values_list('name', flat=True))

    def test_offers_ticked_places_and_the_items_own_customer(self):
        names = self.names()
        self.assertTrue({'TEST GODOWN A', 'TEST PRODUCTION AREA', 'TEST CYL CUSTOMER'} <= names)

    def test_never_offers_another_customer(self):
        self.assertNotIn('TEST OTHER CUSTOMER', self.names())

    def test_a_new_godown_appears_without_any_code_change(self):
        place('TEST GODOWN NEW')
        self.assertIn('TEST GODOWN NEW', self.names())

    def test_an_inactive_place_is_not_offered(self):
        Customer.objects.filter(pk=self.godown.pk).update(active=False)
        self.assertNotIn('TEST GODOWN A', self.names())

    def test_unticking_removes_a_place(self):
        Customer.objects.filter(pk=self.godown.pk).update(is_cylinder_location=False)
        self.assertNotIn('TEST GODOWN A', self.names())

    def test_a_similarly_named_customer_is_not_a_place(self):
        # The old rule matched exact names; the new one matches the flag, so a real
        # customer called e.g. "PRODUCTION HOUSE" is never offered by accident.
        Customer.objects.create(name='TEST PRODUCTION HOUSE PVT LTD')
        self.assertNotIn('TEST PRODUCTION HOUSE PVT LTD', self.names())

    def test_storage_places_come_before_the_customer(self):
        ordered = list(cylinder_locations_for(self.item).values_list('is_cylinder_location', flat=True))
        self.assertEqual(ordered, sorted(ordered, reverse=True))


class MovementFormTests(CylinderLocationBase):
    def test_form_offers_the_helpers_places(self):
        form = CylinderMovementForm(itemmaster=self.item)
        offered = set(form.fields['location'].queryset.values_list('pk', flat=True))
        self.assertEqual(offered, set(cylinder_locations_for(self.item).values_list('pk', flat=True)))

    def test_form_accepts_a_new_godown_and_refuses_a_stranger(self):
        new = place('TEST GODOWN NEW')
        base = {'movementdate': '05/12/2026', 'row': 'A', 'column': 1}
        ok = CylinderMovementForm({**base, 'location': new.pk}, itemmaster=self.item)
        self.assertTrue(ok.is_valid(), ok.errors)
        bad = CylinderMovementForm({**base, 'location': self.other_customer.pk}, itemmaster=self.item)
        self.assertFalse(bad.is_valid())
        self.assertIn('location', bad.errors)


class MovementApiTests(CylinderLocationBase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.payload = {'item': self.item.pk, 'movementdate': '2026-12-05', 'row': 'A', 'column': 1}

    def post(self, location):
        return self.client.post('/api/itemmaster/cylinder-movements/',
                                dict(self.payload, location=location.pk), format='json')

    def test_lookup_lists_the_places_for_an_item(self):
        rows = self.client.get('/api/itemmaster/customer-lookup/',
                               {'cylinder_locations_for_item': self.item.pk, 'page_size': 100}).json()['results']
        names = [r['name'] for r in rows]
        self.assertIn('TEST GODOWN A', names)
        self.assertIn('TEST CYL CUSTOMER', names)
        self.assertNotIn('TEST OTHER CUSTOMER', names)

    def test_lookup_for_an_unknown_item_is_empty(self):
        rows = self.client.get('/api/itemmaster/customer-lookup/',
                               {'cylinder_locations_for_item': 999999999}).json()['results']
        self.assertEqual(rows, [])

    def test_a_movement_to_a_godown_or_the_items_customer_is_accepted(self):
        self.assertEqual(self.post(self.godown).status_code, 201)
        self.assertEqual(self.post(self.customer).status_code, 201)

    def test_a_new_godown_works_straight_away(self):
        self.assertEqual(self.post(place('TEST GODOWN NEW')).status_code, 201)

    def test_a_movement_to_another_customer_is_refused(self):
        response = self.post(self.other_customer)
        self.assertEqual(response.status_code, 400)
        self.assertIn('location', response.json())

    def test_an_inactive_godown_cannot_be_newly_chosen(self):
        Customer.objects.filter(pk=self.godown.pk).update(active=False)
        self.assertEqual(self.post(self.godown).status_code, 400)

    def test_an_old_movement_in_a_deactivated_godown_can_still_be_edited(self):
        movement = CylinderMovement.objects.create(
            item=self.item, location=self.godown, movementdate=datetime.date(2026, 12, 5), row='A', column=1)
        Customer.objects.filter(pk=self.godown.pk).update(active=False)
        response = self.client.patch(f'/api/itemmaster/cylinder-movements/{movement.pk}/',
                                     {'remark': 'edited'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)

    def test_customer_api_exposes_and_sets_the_flag(self):
        response = self.client.patch(f'/api/customer/customers/{self.other_customer.pk}/',
                                     {'is_cylinder_location': True}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['is_cylinder_location'])
        self.assertEqual(self.post(self.other_customer).status_code, 201)


class MarkCommandTests(TestCase):
    def run_command(self, *args):
        out = StringIO()
        call_command('mark_cylinder_locations', *args, stdout=out)
        return out.getvalue()

    def test_ticks_the_three_default_places_by_exact_name(self):
        godown, _ = Customer.objects.get_or_create(name='GODOWN-1', defaults=dict(is_customer=False))
        Customer.objects.filter(pk=godown.pk).update(is_cylinder_location=False)
        house = Customer.objects.create(name='TEST PRODUCTION HOUSE PVT LTD')
        self.run_command()
        godown.refresh_from_db()
        house.refresh_from_db()
        self.assertTrue(godown.is_cylinder_location)
        self.assertFalse(house.is_cylinder_location)

    def test_extra_names_and_dry_run(self):
        extra = Customer.objects.create(name='TEST EXTRA GODOWN')
        self.assertIn('would tick', self.run_command('--name', 'test extra godown', '--dry-run'))
        extra.refresh_from_db()
        self.assertFalse(extra.is_cylinder_location)
        self.run_command('--name', 'test extra godown')
        extra.refresh_from_db()
        self.assertTrue(extra.is_cylinder_location)

    def test_a_missing_name_is_reported_not_an_error(self):
        self.assertIn('no customer with this exact name', self.run_command('--name', 'NO SUCH PLACE'))
