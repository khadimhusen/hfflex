import re

from rest_framework import serializers

from customer.models import Customer
from material.models import Unit
from myproject.thumbnails import get_or_create_thumbnail
from .models import PreOrder, JobName
from .querysets import can_edit_preorder

# Same pattern as AddPreOrderForm's HTML `pattern` attribute: a standard
# 15-character GST number, or the literal "URP" (unregistered person) or
# "As Per Master" placeholders — normalized case-insensitively here rather
# than requiring the exact mixed case the old HTML pattern demanded.
GST_REGEX = re.compile(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$')
GST_LITERALS = {'URP', 'AS PER MASTER'}


class CustomerLookupSerializer(serializers.ModelSerializer):
    """Minimal customer lookup for the preorder 'customer' field's
    autocomplete — scoped to IsPreorderUser rather than the customer
    module's own IsCustomerUser, same reasoning as itemmaster's."""

    class Meta:
        model = Customer
        fields = ['id', 'name']


class UnitLookupSerializer(serializers.ModelSerializer):
    """Minimal unit lookup for JobName's unit dropdown — material is
    staff-only, which almost no preorder user would satisfy."""

    class Meta:
        model = Unit
        fields = ['id', 'unit']


class JobNameSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)
    edited_by_name = serializers.CharField(source='editedby.get_full_name', read_only=True, default=None)
    unit_display = serializers.CharField(source='unit.unit', read_only=True)
    preorder_customer = serializers.CharField(source='preorder.customer', read_only=True)
    job_status = serializers.CharField(read_only=True)
    is_done = serializers.SerializerMethodField()
    preimg_thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = JobName
        fields = [
            'id', 'preorder', 'preorder_customer', 'jobname', 'qty', 'unit', 'unit_display', 'new_cyl_qty',
            'new_cylinder', 'cyl_invoice', 'cyl_cost', 'design_charges', 'rate',
            'preimg', 'preimg_thumbnail_url', 'prefile', 'remark', 'job_status', 'is_done',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby', 'edited_by_name',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']

    def get_is_done(self, obj):
        return hasattr(obj, 'job') and obj.job is not None

    def get_preimg_thumbnail_url(self, obj):
        url = get_or_create_thumbnail(obj.preimg)
        if not url:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url


class PreOrderSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)
    edited_by_name = serializers.CharField(source='editedby.get_full_name', read_only=True, default=None)
    done = serializers.ReadOnlyField()
    can_edit = serializers.SerializerMethodField()
    jobname_count = serializers.IntegerField(source='jobname.count', read_only=True)

    class Meta:
        model = PreOrder
        fields = [
            'id', 'customer', 'address', 'gst', 'contact_number', 'schedule',
            'final_submition', 'is_locked', 'done', 'can_edit', 'jobname_count',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby', 'edited_by_name',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']

    def validate_gst(self, value):
        normalized = value.strip().upper()
        if normalized in GST_LITERALS:
            return normalized.title() if normalized == 'AS PER MASTER' else normalized
        if not GST_REGEX.match(normalized):
            raise serializers.ValidationError(
                "Enter a valid 15-character GST number, or 'URP' / 'As Per Master'."
            )
        return normalized

    def get_can_edit(self, obj):
        if obj.pk is None:
            return True
        request = self.context.get('request')
        if not request:
            return False
        return can_edit_preorder(request.user, obj)
