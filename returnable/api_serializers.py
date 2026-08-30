from rest_framework import serializers

from customer.models import Customer, Address
from material.models import Unit
from .models import Returnable, ChallanItem, ReceivedChallan, ReceivedItem


class CustomerLookupSerializer(serializers.ModelSerializer):
    """For Returnable/ReceivedChallan.party_name -- old ReturnableForm/
    ReceivedChallanForm both scoped this to active suppliers only."""

    class Meta:
        model = Customer
        fields = ['id', 'name']


class AddressLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id', 'addname', 'add1', 'add2', 'pincode']


class UnitLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ['id', 'unit']


class ChallanItemSerializer(serializers.ModelSerializer):
    unit_display = serializers.CharField(source='unit.unit', read_only=True)
    receivedqty = serializers.ReadOnlyField()
    pendingqty = serializers.ReadOnlyField()

    class Meta:
        model = ChallanItem
        fields = [
            'id', 'returnable', 'itemname', 'description', 'category', 'qty', 'unit', 'unit_display',
            'approxvalue', 'receivedqty', 'pendingqty',
            'created', 'createdby', 'edited', 'editedby',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']


class ReturnableListSerializer(serializers.ModelSerializer):
    """Lightweight row for returnablelist.html's table."""
    party_name_display = serializers.CharField(source='party_name.name', read_only=True)
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)

    class Meta:
        model = Returnable
        fields = [
            'id', 'party_name', 'party_name_display', 'status', 'expected_date',
            'created', 'created_by_name',
        ]


class ReturnableSerializer(serializers.ModelSerializer):
    """Mirrors ReturnableForm. Challan items are their own sub-resource
    (ChallanItemViewSet, filtered by ?returnable=<id>) rather than nested
    here -- same pattern as order.Job/JobMaterial."""
    party_name_display = serializers.CharField(source='party_name.name', read_only=True)
    address_display = serializers.CharField(source='address.addname', read_only=True, default=None)
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)
    edited_by_name = serializers.CharField(source='editedby.get_full_name', read_only=True, default=None)
    totalamount = serializers.ReadOnlyField()
    totalqty = serializers.ReadOnlyField()
    total_rec_qty = serializers.ReadOnlyField()
    totalpendingqty = serializers.ReadOnlyField()

    class Meta:
        model = Returnable
        fields = [
            'id', 'party_name', 'party_name_display', 'address', 'address_display',
            'dispatch_date', 'expected_date', 'receivedby', 'contact', 'recieptnumber',
            'transportby', 'person', 'vehicle', 'remark', 'status', 'lock',
            'totalamount', 'totalqty', 'total_rec_qty', 'totalpendingqty',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby', 'edited_by_name',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']


class ReceivedItemSerializer(serializers.ModelSerializer):
    unit_display = serializers.CharField(source='unit.unit', read_only=True)
    challan_item_name = serializers.CharField(source='received_item.itemname', read_only=True)
    returnable_id = serializers.IntegerField(source='received_item.returnable_id', read_only=True)

    class Meta:
        model = ReceivedItem
        fields = [
            'id', 'received_challan', 'received_item', 'challan_item_name', 'returnable_id',
            'qty', 'unit', 'unit_display', 'status',
            'created', 'createdby', 'edited', 'editedby',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']


class ReceivedChallanListSerializer(serializers.ModelSerializer):
    party_name_display = serializers.CharField(source='party_name.name', read_only=True)
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)

    class Meta:
        model = ReceivedChallan
        fields = ['id', 'party_name', 'party_name_display', 'received_date', 'transport', 'recieptnumber', 'remark', 'created_by_name']


class ReceivedChallanSerializer(serializers.ModelSerializer):
    """Mirrors ReceivedChallanForm. Received items are their own
    sub-resource (ReceivedItemViewSet, filtered by ?received_challan=<id>)."""
    party_name_display = serializers.CharField(source='party_name.name', read_only=True)
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)
    edited_by_name = serializers.CharField(source='editedby.get_full_name', read_only=True, default=None)

    class Meta:
        model = ReceivedChallan
        fields = [
            'id', 'party_name', 'party_name_display', 'received_date', 'transport', 'recieptnumber', 'remark',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby', 'edited_by_name',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']
