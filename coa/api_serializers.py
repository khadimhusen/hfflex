from rest_framework import serializers

from order.models import JobCoa
from production.models import DispatchRegister
from .models import Coa, TestParameter


class DispatchRegisterLookupSerializer(serializers.ModelSerializer):
    """For Coa.delivery_challan's admin-edit dropdown. Not scoped to a
    single job -- Stockdetail links back to its job via a GenericForeignKey
    (job_disptached), not a plain FK, so cheaply scoping this list to "only
    this job's own dispatches" isn't a simple filter; the old app's own
    CoaForm didn't scope this list either. Kept simple and ordered
    newest-first, since this dropdown is only ever used for the rare
    after-the-fact correction (coa_admin_edit) -- the normal flow sets
    delivery_challan from context (the dispatch row "Add COA" was clicked
    from), never through this dropdown."""
    customer_name = serializers.CharField(source='customer.name', read_only=True)

    class Meta:
        model = DispatchRegister
        fields = ['id', 'customer_name', 'dispatchdate']


class TestParameterSerializer(serializers.ModelSerializer):
    standard_parameter_display = serializers.CharField(source='standard_parameter.parameter', read_only=True)
    unit_of_measure = serializers.CharField(source='standard_parameter.unit_of_measure', read_only=True)

    class Meta:
        model = TestParameter
        fields = ['id', 'coa', 'standard_parameter', 'standard_parameter_display', 'unit_of_measure', 'result']

    def validate(self, attrs):
        # Mirrors TestParameterForm's queryset scoping: only parameters the
        # job's own COA spec sheet (JobCoa) actually lists, and only while
        # the parent COA is still unapproved (coa_edit's hard block).
        coa = attrs.get('coa') or (self.instance.coa if self.instance else None)
        standard_parameter = attrs.get('standard_parameter') or (
            self.instance.standard_parameter if self.instance else None
        )
        if coa and coa.is_approved:
            raise serializers.ValidationError(f'COA {coa.coa_number} is already approved and cannot be edited.')
        if coa and standard_parameter:
            allowed = JobCoa.objects.filter(job=coa.jobname).values_list('standard_parameter_id', flat=True)
            if standard_parameter.id not in allowed:
                raise serializers.ValidationError(
                    {'standard_parameter': "This parameter isn't in the job's own COA spec sheet."},
                )
        return attrs


class CoaSerializer(serializers.ModelSerializer):
    """Mirrors CoaForm (unapproved) / CoaAdminForm (approved) as one
    serializer instead of two: once approved, everything except the four
    admin fields (work_order/delivery_challan/invoice_no/qty) becomes
    read-only automatically (see __init__) rather than needing a caller to
    know which form to use -- same conditional-read-only convention as
    order.JobSerializer's itemmaster/prejob fields."""
    coa_number = serializers.ReadOnlyField()
    is_approved = serializers.ReadOnlyField()
    approver_name = serializers.ReadOnlyField()
    jobname_display = serializers.CharField(source='jobname.itemname', read_only=True)
    delivery_challan_display = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)
    edited_by_name = serializers.CharField(source='editedby.get_full_name', read_only=True, default=None)

    class Meta:
        model = Coa
        fields = [
            'id', 'coa_number', 'jobname', 'jobname_display', 'work_order', 'delivery_challan',
            'delivery_challan_display', 'invoice_no', 'qty', 'remark',
            'shelf_life_months', 'storage_conditions',
            'is_approved', 'approvedby', 'approver_name', 'approve_date',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby', 'edited_by_name',
        ]
        read_only_fields = [
            'jobname', 'is_approved', 'approvedby', 'approve_date',
            'created', 'createdby', 'edited', 'editedby',
        ]

    def get_delivery_challan_display(self, obj):
        return str(obj.delivery_challan) if obj.delivery_challan_id else None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # jobname is always read-only (set once at creation, see the
        # viewset) -- only lock the *rest* of the editable fields down to
        # the admin-only subset once the COA is actually approved.
        if self.instance is not None and getattr(self.instance, 'is_approved', False):
            # Everything except the four admin fields locks once approved.
            for name in ('remark', 'shelf_life_months', 'storage_conditions'):
                self.fields[name].read_only = True
