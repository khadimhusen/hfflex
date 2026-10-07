from django.test import Client
from rest_framework.test import APIClient

from company.models import Company
from customer.models import Address, Customer
from purchase.forms import PoForm
from purchase.models import Po
from purchase.pdfviews import build_po_pdf_buffer
from purchase.test_buyer import BuyerTestBase, ensure_default, make_po, other_company


def linked_company(short_name='TL', name='TEST LINKED PVT. LTD.'):
    """A company with its own customer record and two addresses ('A Factory' sorts first)."""
    customer, _ = Customer.objects.get_or_create(name=name, defaults=dict(gst=None, is_customer=False))
    Address.objects.get_or_create(customer=customer, addname='B Office', defaults=dict(add1='Pune'))
    Address.objects.get_or_create(customer=customer, addname='A Factory', defaults=dict(add1='Sangli'))
    company = other_company(name=name, short_name=short_name)
    Company.objects.filter(pk=company.pk).update(customer=customer)
    company.refresh_from_db()
    return company


class DeliveryFollowsBuyerTests(BuyerTestBase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        self.payload = {'supplier': self.supplier.id, 'delivery_date': '2026-12-01T10:00:00'}
        self.default = ensure_default()
        self.linked = linked_company()
        self.hf_customer = Customer.objects.get(name='H F FLEX PRIVATE LIMITED')
        self.hf_address = Address.objects.get_or_create(
            customer=self.hf_customer, addname='Factory:-', defaults=dict(add1='Gardi'))[0]

    def post(self, **extra):
        return self.client.post('/api/purchase/purchase-orders/', dict(self.payload, **extra), format='json')

    def test_new_order_ships_to_the_buyers_own_customer_and_first_address(self):
        response = self.post(buyer=self.linked.pk)
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body['ship_to'], self.linked.customer_id)
        self.assertEqual(Address.objects.get(pk=body['delivery_at']).addname, 'A Factory')

    def test_an_address_of_another_company_is_refused(self):
        response = self.post(buyer=self.linked.pk, delivery_at=self.hf_address.pk)
        self.assertEqual(response.status_code, 400)
        self.assertIn('delivery_at', response.json())

    def test_a_chosen_address_of_the_buyer_is_kept(self):
        other = Address.objects.get(customer=self.linked.customer, addname='B Office')
        response = self.post(buyer=self.linked.pk, delivery_at=other.pk)
        self.assertEqual(response.json()['delivery_at'], other.pk)

    def test_a_company_with_no_customer_record_leaves_them_empty(self):
        bare = other_company(name='TEST BARE PVT. LTD.', short_name='TB')
        response = self.post(buyer=bare.pk)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertIsNone(response.json()['ship_to'])
        self.assertIsNone(response.json()['delivery_at'])

    def test_changing_the_buyer_moves_ship_to_and_address_with_it(self):
        Company.objects.filter(pk=self.default.pk).update(customer=self.hf_customer)
        po = make_po(self.supplier, buyer=self.default, ship_to=self.hf_customer, delivery_at=self.hf_address)
        response = self.client.patch(
            f'/api/purchase/purchase-orders/{po.pk}/', {'buyer': self.linked.pk}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        po.refresh_from_db()
        self.assertEqual(po.ship_to_id, self.linked.customer_id)
        self.assertEqual(po.delivery_at.addname, 'A Factory')

    def test_changing_the_buyer_leaves_an_outside_ship_to_alone(self):
        Company.objects.filter(pk=self.default.pk).update(customer=self.hf_customer)
        outside = Customer.objects.get_or_create(name='TEST OUTSIDE PARTY', defaults=dict(is_supplier=True))[0]
        po = make_po(self.supplier, buyer=self.default, ship_to=outside, delivery_at=self.hf_address)
        response = self.client.patch(
            f'/api/purchase/purchase-orders/{po.pk}/', {'buyer': self.linked.pk}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        po.refresh_from_db()
        self.assertEqual(po.ship_to, outside)

    def test_editing_something_else_does_not_touch_ship_to_or_address(self):
        po = make_po(self.supplier, buyer=self.linked, ship_to=self.hf_customer, delivery_at=self.hf_address)
        response = self.client.patch(f'/api/purchase/purchase-orders/{po.pk}/', {'remark': 'x'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        po.refresh_from_db()
        self.assertEqual((po.ship_to, po.delivery_at), (self.hf_customer, self.hf_address))

    def test_address_lookup_for_a_buyer(self):
        rows = self.client.get('/api/purchase/delivery-address-lookup/',
                               {'buyer': self.linked.pk, 'page_size': 50}).json()['results']
        self.assertEqual([r['addname'] for r in rows], ['A Factory', 'B Office'])

    def test_address_lookup_without_a_buyer_is_still_h_f_flex(self):
        rows = self.client.get('/api/purchase/delivery-address-lookup/', {'page_size': 500}).json()['results']
        self.assertEqual({r['id'] for r in rows},
                         set(Address.objects.filter(customer_id=31).values_list('pk', flat=True)))

    def test_buyer_lookup_carries_the_customer(self):
        rows = {r['id']: r for r in self.client.get('/api/purchase/buyer-lookup/').json()['results']}
        self.assertEqual(rows[self.linked.pk]['customer'], self.linked.customer_id)
        self.assertEqual(rows[self.linked.pk]['customer_name'], 'TEST LINKED PVT. LTD.')

    def test_cloning_keeps_the_buyer_and_where_it_ships(self):
        po = make_po(self.supplier, buyer=self.linked, ship_to=self.linked.customer,
                     delivery_at=self.linked.delivery_addresses().first())
        response = self.client.post(f'/api/purchase/purchase-orders/{po.pk}/clone/')
        self.assertEqual(response.status_code, 201, response.content)
        copy = Po.objects.get(pk=response.json()['id'])
        self.assertEqual((copy.buyer, copy.ship_to, copy.delivery_at), (po.buyer, po.ship_to, po.delivery_at))

    def test_pdf_prints_an_order_with_no_ship_to_or_address(self):
        bare = other_company(name='TEST BARE PVT. LTD.', short_name='TB')
        po = make_po(self.supplier, buyer=bare, ship_to=None)
        self.assertGreater(len(build_po_pdf_buffer(po).getvalue()), 1000)

    def test_old_app_helper_returns_the_buyers_addresses(self):
        c = Client()
        c.force_login(self.staff)
        data = c.get('/purchase/buyerdelivery/', {'buyer': self.linked.pk}).json()
        self.assertEqual(data['customer'], self.linked.customer_id)
        self.assertEqual([a['label'] for a in data['addresses']], ['A Factory - Sangli', 'B Office - Pune'])


class OldFormFollowsBuyerTests(BuyerTestBase):
    def test_form_offers_the_posted_buyers_addresses_and_fills_ship_to(self):
        ensure_default()
        linked = linked_company()
        form = PoForm({'buyer': linked.pk})
        offered = set(form.fields['delivery_at'].queryset.values_list('addname', flat=True))
        self.assertEqual(offered, {'A Factory', 'B Office'})
        form.is_valid()
        self.assertEqual(form.cleaned_data['ship_to'], linked.customer)

    def test_an_address_of_another_company_is_not_a_valid_choice(self):
        ensure_default()
        linked = linked_company()
        stranger = Address.objects.get_or_create(
            customer=Customer.objects.get(name='H F FLEX PRIVATE LIMITED'),
            addname='Stranger', defaults=dict(add1='x'))[0]
        form = PoForm({'buyer': linked.pk, 'delivery_at': stranger.pk})
        form.is_valid()
        self.assertIn('delivery_at', form.errors)
