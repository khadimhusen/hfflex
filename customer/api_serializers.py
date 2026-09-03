import re

from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Customer, Address, Person, Pincode
from .querysets import marketing_users

# Standard 15-character GST number: 2-digit state code, 10-char PAN,
# 1-digit entity code, fixed 'Z', 1 alphanumeric checksum.
GST_REGEX = re.compile(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$')


class MarketingUserSerializer(serializers.ModelSerializer):
    """Just for populating the marketing_person dropdown in the frontend —
    never exposes anything beyond name/username, mirroring CrmUserSerializer."""

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']


class PincodeSerializer(serializers.ModelSerializer):
    """Powers the place-name typeahead on Find Nearby Customers -- pick a
    result here to fill in its pincode rather than needing to know it."""

    class Meta:
        model = Pincode
        fields = ['code', 'place_name', 'district', 'state']


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = [
            'id', 'customer', 'addname', 'add1', 'add2', 'pincode', 'phone', 'remark',
            'created', 'createdby', 'edited', 'editedby',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = [
            'id', 'customer', 'name', 'designation', 'mobile', 'email', 'remark',
            'created', 'createdby', 'edited', 'editedby',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']


class CustomerSerializer(serializers.ModelSerializer):
    # Declared explicitly (rather than relying on the model's limit_choices_to)
    # to match how crm.OwnerSerializerMixin scopes its owner field.
    marketing_person = serializers.PrimaryKeyRelatedField(
        queryset=marketing_users(), required=False, allow_null=True,
    )
    marketing_person_name = serializers.CharField(
        source='marketing_person.get_full_name', read_only=True, default=None,
    )
    created_by_name = serializers.CharField(
        source='createdby.get_full_name', read_only=True, default=None,
    )
    address_count = serializers.IntegerField(source='addresses.count', read_only=True)
    person_count = serializers.IntegerField(source='persons.count', read_only=True)

    class Meta:
        model = Customer
        fields = [
            'id', 'name', 'gst', 'is_customer', 'is_supplier', 'email',
            'marketing_person', 'marketing_person_name', 'active',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby',
            'address_count', 'person_count',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']

    def validate_gst(self, value):
        if not value:
            return value
        value = value.strip().upper()
        if not GST_REGEX.match(value):
            raise serializers.ValidationError(
                'Enter a valid 15-character GST number, e.g. 27AAAAA0000A1Z5.'
            )
        return value
