from rest_framework import viewsets
from rest_framework.exceptions import ValidationError

from customer.models import Customer, Address
from material.models import Unit
from .models import Returnable, ChallanItem, ReceivedChallan, ReceivedItem
from .api_serializers import (
    CustomerLookupSerializer, AddressLookupSerializer, UnitLookupSerializer,
    ReturnableListSerializer, ReturnableSerializer, ChallanItemSerializer,
    ReceivedChallanListSerializer, ReceivedChallanSerializer, ReceivedItemSerializer,
)
from .permissions import IsReturnableUser


class CustomerLookupViewSet(viewsets.ReadOnlyModelViewSet):
    """Mirrors ReturnableForm/ReceivedChallanForm's party_name queryset:
    active suppliers only, scoped to IsReturnableUser rather than the
    customer module's own permission class, same reasoning as every other
    module's own lookup."""
    queryset = Customer.objects.filter(active=True, is_supplier=True).order_by('name')
    serializer_class = CustomerLookupSerializer
    permission_classes = [IsReturnableUser]


class AddressLookupViewSet(viewsets.ReadOnlyModelViewSet):
    """Mirrors the old ajax_load_address endpoint -- filter by ?customer=."""
    serializer_class = AddressLookupSerializer
    permission_classes = [IsReturnableUser]
    filterset_fields = ['customer']
    queryset = Address.objects.order_by('addname')


class UnitLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Unit.objects.order_by('unit')
    serializer_class = UnitLookupSerializer
    permission_classes = [IsReturnableUser]


class ReturnableViewSet(viewsets.ModelViewSet):
    queryset = Returnable.objects.select_related('party_name', 'address', 'createdby', 'editedby').order_by('-id')
    permission_classes = [IsReturnableUser]
    filterset_fields = ['party_name', 'status', 'createdby']

    def get_serializer_class(self):
        if self.action == 'list':
            return ReturnableListSerializer
        return ReturnableSerializer

    def perform_create(self, serializer):
        # Mirrors returnablenew(): every new challan starts life as
        # "Dispatched", regardless of what (if anything) was submitted --
        # the old view hardcoded this the same way.
        serializer.save(createdby=self.request.user, status='Dispatched')

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)


class ChallanItemViewSet(viewsets.ModelViewSet):
    queryset = ChallanItem.objects.select_related('returnable', 'unit', 'createdby', 'editedby').order_by('id')
    serializer_class = ChallanItemSerializer
    permission_classes = [IsReturnableUser]
    filterset_fields = ['returnable']

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)

    def get_queryset(self):
        qs = super().get_queryset()
        # Mirrors ReceivedItemForm's received_item queryset: items
        # belonging to the given party's challans still Dispatched/
        # Delivered/Partially received -- feeds the "pick items to
        # receive back" step of the received-challan form.
        party = self.request.query_params.get('pending_for_party')
        if party:
            qs = qs.filter(
                returnable__party_name_id=party,
                returnable__status__in=['Dispatched', 'Delivered', 'Partially received'],
            )
        return qs


class ReceivedChallanViewSet(viewsets.ModelViewSet):
    queryset = ReceivedChallan.objects.select_related('party_name', 'createdby', 'editedby').order_by('-id')
    permission_classes = [IsReturnableUser]
    filterset_fields = ['party_name', 'createdby']

    def get_serializer_class(self):
        if self.action == 'list':
            return ReceivedChallanListSerializer
        return ReceivedChallanSerializer

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)


class ReceivedItemViewSet(viewsets.ModelViewSet):
    queryset = ReceivedItem.objects.select_related(
        'received_challan', 'received_item', 'received_item__returnable', 'unit', 'createdby', 'editedby',
    ).order_by('id')
    serializer_class = ReceivedItemSerializer
    permission_classes = [IsReturnableUser]
    filterset_fields = ['received_challan']

    def perform_create(self, serializer):
        received_item = serializer.validated_data.get('received_item')
        qty = serializer.validated_data.get('qty')
        if received_item and qty is not None and qty > received_item.pendingqty:
            raise ValidationError({'qty': f'Only {received_item.pendingqty} pending for this item.'})
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.instance
        received_item = serializer.validated_data.get('received_item', instance.received_item)
        qty = serializer.validated_data.get('qty', instance.qty)
        # pendingqty already excludes this row's own previous qty from the
        # "already received" side of the sum, so add it back before
        # comparing against the new qty being submitted for this same row.
        already_pending = received_item.pendingqty + instance.qty if received_item == instance.received_item else received_item.pendingqty
        if qty > already_pending:
            raise ValidationError({'qty': f'Only {already_pending} pending for this item.'})
        serializer.save(editedby=self.request.user)
