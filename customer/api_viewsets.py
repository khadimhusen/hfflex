from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Customer, Address, Person, Pincode
from .api_serializers import (
    CustomerSerializer, AddressSerializer, PersonSerializer, MarketingUserSerializer,
)
from .filters import CustomerFilter
from .querysets import marketing_users
from .permissions import IsCustomerUser
from .utils import haversine_km


class MarketingUserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = marketing_users()
    serializer_class = MarketingUserSerializer
    permission_classes = [IsCustomerUser]


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.select_related('marketing_person', 'createdby', 'editedby')
    serializer_class = CustomerSerializer
    filterset_class = CustomerFilter
    # addresses__add1/add2 let the one search box also match a customer's
    # address/location -- 'addresses' is a to-many reverse FK, so DRF's
    # SearchFilter auto-applies .distinct() to avoid duplicate rows from a
    # customer with multiple matching addresses.
    search_fields = ['name', 'gst', 'email', 'addresses__add1', 'addresses__add2']
    permission_classes = [IsCustomerUser]

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)

    @action(detail=False, methods=['get'])
    def nearby(self, request):
        """Customers within radius_km of the given pincode -- e.g. 'we got
        an enquiry from Mayni, who's our nearest customer we can point them
        to?' One row per matching Address (a customer with two addresses in
        range appears twice -- that's useful, it says which branch is
        close), sorted nearest first. Distance is haversine great-circle,
        not road distance -- a ballpark reference, not turn-by-turn.
        """
        raw_pincode = (request.query_params.get('pincode') or '').strip()
        if not raw_pincode.isdigit() or len(raw_pincode) != 6:
            return Response({'pincode': ['Enter a valid 6-digit pincode.']}, status=400)
        pincode = int(raw_pincode)

        try:
            radius_km = float(request.query_params.get('radius_km', 100))
        except ValueError:
            return Response({'radius_km': ['Must be a number.']}, status=400)
        if radius_km <= 0:
            return Response({'radius_km': ['Must be greater than 0.']}, status=400)

        origin = Pincode.objects.filter(code=pincode).first()
        if origin is None:
            return Response(
                {'pincode': ['Unknown pincode -- not in the India Post directory.']}, status=400,
            )

        # Distinct pincodes actually in use on customer addresses -- a few
        # hundred/thousand at most, nowhere near the full ~19k pincode
        # table, so doing the haversine pass in Python here (rather than
        # needing PostGIS) stays cheap.
        used_pincodes = Address.objects.exclude(pincode__isnull=True).values_list('pincode', flat=True).distinct()
        candidates = Pincode.objects.filter(code__in=used_pincodes)

        origin_lat, origin_lng = float(origin.latitude), float(origin.longitude)
        distance_by_pincode = {}
        for c in candidates:
            d = haversine_km(origin_lat, origin_lng, float(c.latitude), float(c.longitude))
            if d <= radius_km:
                distance_by_pincode[c.code] = round(d, 1)

        addresses = (
            Address.objects.filter(pincode__in=distance_by_pincode.keys(), customer__active=True)
            .select_related('customer', 'customer__marketing_person')
        )

        results = [
            {
                'distance_km': distance_by_pincode[a.pincode],
                'customer_id': a.customer_id,
                'customer_name': a.customer.name,
                'is_customer': a.customer.is_customer,
                'is_supplier': a.customer.is_supplier,
                'marketing_person_name': (
                    a.customer.marketing_person.get_full_name() if a.customer.marketing_person else None
                ),
                'address_id': a.id,
                'addname': a.addname,
                'add1': a.add1,
                'add2': a.add2,
                'pincode': a.pincode,
                'phone': a.phone,
            }
            for a in addresses
        ]
        results.sort(key=lambda r: (r['distance_km'], r['customer_name']))

        return Response({
            'origin': {
                'pincode': origin.code,
                'place_name': origin.place_name,
                'district': origin.district,
                'state': origin.state,
            },
            'radius_km': radius_km,
            'count': len(results),
            'results': results,
        })


class AddressViewSet(viewsets.ModelViewSet):
    queryset = Address.objects.select_related('customer', 'createdby', 'editedby')
    serializer_class = AddressSerializer
    filterset_fields = ['customer']
    permission_classes = [IsCustomerUser]

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)


class PersonViewSet(viewsets.ModelViewSet):
    queryset = Person.objects.select_related('customer', 'createdby', 'editedby')
    serializer_class = PersonSerializer
    filterset_fields = ['customer']
    permission_classes = [IsCustomerUser]

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)
