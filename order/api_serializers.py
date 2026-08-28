from django.contrib.auth.models import User
from rest_framework import serializers

from customer.models import Customer, Address
from material.models import Unit
from itemmaster.models import ItemMaster
from preorder.models import JobName
from .models import Order, Job
from .querysets import can_edit_order


class CustomerLookupSerializer(serializers.ModelSerializer):
    """Minimal customer lookup for Order.customer — scoped to IsOrderUser
    rather than the customer module's own IsCustomerUser, same reasoning
    as every other module's own lookup."""

    class Meta:
        model = Customer
        fields = ['id', 'name']


class AddressLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id', 'addname', 'add1', 'add2', 'pincode']


class MarketingPersonLookupSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        return obj.get_full_name() or obj.username


class UnitLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ['id', 'unit']


class ItemMasterLookupSerializer(serializers.ModelSerializer):
    """For Job.itemmaster — old JobForm scoped this to the ORDER's own
    customer's active items only."""

    class Meta:
        model = ItemMaster
        fields = ['id', 'itemname', 'itemcode']


class PrejobLookupSerializer(serializers.ModelSerializer):
    """For Job.prejob — old JobForm scoped this to preorder JobNames that
    are final-submitted and not yet converted into a Job."""
    unit_display = serializers.CharField(source='unit.unit', read_only=True)

    class Meta:
        model = JobName
        fields = ['id', 'jobname', 'qty', 'unit_display']


class OrderSerializer(serializers.ModelSerializer):
    # The model allows null (blank=True, null=True), but the old OrderForm
    # required both as plain DateTimeFields — same class of gotcha as
    # purchase.Po.delivery_date.
    podate = serializers.DateTimeField(required=True)
    deliverydate = serializers.DateTimeField(required=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    delivery_at_display = serializers.CharField(source='delivery_at.addname', read_only=True, default=None)
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)
    edited_by_name = serializers.CharField(source='editedby.get_full_name', read_only=True, default=None)
    jobcount = serializers.IntegerField(source='job.count', read_only=True)
    can_edit = serializers.SerializerMethodField()
    # Not a model field — old OrderForm's marketing_person is really a
    # side-channel write to Customer.marketing_person (see perform_create/
    # perform_update), kept here only so the SPA can submit it in the same
    # request as the rest of the order form.
    marketing_person = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.none(), required=False, write_only=True, allow_null=True,
    )

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'customer_name', 'po', 'podate', 'deliverydate', 'paymentterms',
            'tax1', 'tax2', 'transport', 'remark', 'delivery_at', 'delivery_at_display', 'status',
            'jobcount', 'can_edit', 'marketing_person',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby', 'edited_by_name',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['marketing_person'].queryset = User.objects.filter(
            department__department_name='marketing', is_active=True,
        )

    def get_can_edit(self, obj):
        if obj.pk is None:
            return True
        request = self.context.get('request')
        if not request:
            return False
        return can_edit_order(request.user, obj)


class JobSerializer(serializers.ModelSerializer):
    """Mirrors JobForm (create: prejob/itemmaster/quantity/unit/rate/waste/
    jobremark) and JobDetailEditForm (edit: everything except joborder/
    itemmaster/prejob/approvedby/account_clearance_date) — 'itemmaster'
    and 'prejob' are writable on create only (see __init__), matching that
    split exactly rather than folding both old forms into one all-writable
    serializer.

    The heavy lifting — copying ~20 spec fields down from ItemMaster and
    auto-creating JobMaterial/JobColor/JobImage/JobItemAttribute/
    JobProcess/JobCoa rows — all already lives in Job.save() itself, so
    perform_create() below needs nothing beyond stamping createdby; the
    model does the rest exactly as it already does for the old app.
    """

    itemname_display = serializers.CharField(source='itemname', read_only=True)
    unit_display = serializers.CharField(source='unit.unit', read_only=True)
    order_customer = serializers.CharField(source='joborder.customer.name', read_only=True)
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)
    edited_by_name = serializers.CharField(source='editedby.get_full_name', read_only=True, default=None)
    marketing_person_name = serializers.CharField(
        source='marketing_person.get_full_name', read_only=True, default=None,
    )
    approvedby_name = serializers.CharField(source='approvedby.get_full_name', read_only=True, default=None)

    # --- cheap-ish computed properties (safe for list + detail) ---
    ply = serializers.ReadOnlyField()
    pouchqty = serializers.ReadOnlyField()
    kgrate = serializers.ReadOnlyField()
    late = serializers.SerializerMethodField()
    nearschedule = serializers.SerializerMethodField()
    oneweek = serializers.SerializerMethodField()
    twoweek = serializers.SerializerMethodField()

    # --- expensive computed properties (detail only — each one walks
    # jobmaterial/jobprocess/prodreport/prodinput; fine for a single job,
    # an N+1 risk across a list of hundreds) ---
    totalgsm = serializers.SerializerMethodField()
    totalmicron = serializers.SerializerMethodField()
    std_waste_percentage = serializers.SerializerMethodField()
    jobwaste = serializers.SerializerMethodField()
    cost = serializers.SerializerMethodField()
    salecost = serializers.SerializerMethodField()
    profit = serializers.SerializerMethodField()
    netoutput = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            'id', 'prejob', 'joborder', 'order_customer', 'itemmaster', 'itemname_display',
            'quantity', 'unit', 'unit_display', 'rate', 'waste', 'jobstatus',
            'account_clearance_date', 'approvedby', 'approvedby_name',
            'marketing_person', 'marketing_person_name',
            'dispatch_approval', 'dispatch_approval_date', 'dispatch_remark', 'jobremark',
            'kgqty', 'itemname', 'invoice', 'barcode', 'packsize',
            'replength', 'openwidth', 'slit_size', 'no_of_repeat', 'no_of_ups',
            'cyl_length', 'cyl_circum', 'printing', 'total_gsm', 'pouch_weight', 'pouch_per_kg',
            'pouch_type', 'supply_form', 'film_size', 'remark', 'unwind_direction', 'lami_rubber',
            'totalpouch', 'totalmeter', 'job_waste', 'job_repeat_status', 'calculated_waste_percentage',
            'ply', 'pouchqty', 'kgrate', 'late', 'nearschedule', 'oneweek', 'twoweek',
            'totalgsm', 'totalmicron', 'std_waste_percentage', 'jobwaste', 'cost', 'salecost',
            'profit', 'netoutput',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby', 'edited_by_name',
        ]
        read_only_fields = [
            'account_clearance_date', 'approvedby',
            # Recomputed unconditionally in Job.save() from current field
            # values every time an existing job is saved — submitting a
            # value for these is silently overwritten, so treat them as
            # the computed fields they actually are.
            'total_gsm', 'pouch_weight', 'pouch_per_kg', 'kgqty', 'totalpouch', 'totalmeter',
            'job_waste', 'calculated_waste_percentage',
            'created', 'createdby', 'edited', 'editedby',
        ]

    # Snapshot fields Job.save()'s create branch unconditionally copies
    # down from itemmaster, discarding anything submitted — JobForm never
    # even collects them. Freely editable afterward though: the update
    # branch doesn't re-copy from itemmaster, and JobDetailEditForm does
    # include all of these. So: read-only (and therefore not required) on
    # create, normally writable on update — the mirror image of
    # itemmaster/prejob just above.
    _AUTOFILLED_ON_CREATE = [
        'itemname', 'barcode', 'packsize', 'replength', 'openwidth', 'slit_size', 'no_of_repeat',
        'no_of_ups', 'cyl_length', 'cyl_circum', 'printing', 'pouch_type', 'supply_form', 'film_size',
        'unwind_direction', 'lami_rubber', 'marketing_person',
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            # itemmaster/prejob: writable on create (JobForm), fixed
            # forever after (JobDetailEditForm excludes both).
            self.fields['itemmaster'].read_only = True
            self.fields['prejob'].read_only = True
        else:
            for name in self._AUTOFILLED_ON_CREATE:
                self.fields[name].read_only = True

    def get_late(self, obj):
        return bool(obj.joborder.deliverydate) and obj.late

    def get_nearschedule(self, obj):
        return bool(obj.joborder.deliverydate) and obj.nearschedule

    def get_oneweek(self, obj):
        return bool(obj.joborder.deliverydate) and obj.oneweek

    def get_twoweek(self, obj):
        return bool(obj.joborder.deliverydate) and obj.twoweek

    def _detail(self):
        return self.context.get('detail', False)

    def get_totalgsm(self, obj):
        return obj.totalgsm if self._detail() else None

    def get_totalmicron(self, obj):
        return obj.totalmicron if self._detail() else None

    def get_std_waste_percentage(self, obj):
        return obj.std_waste_percentage if self._detail() else None

    def get_jobwaste(self, obj):
        return obj.jobwaste if self._detail() else None

    def get_cost(self, obj):
        return obj.cost if self._detail() else None

    def get_salecost(self, obj):
        return obj.salecost if self._detail() else None

    def get_profit(self, obj):
        return obj.profit if self._detail() else None

    def get_netoutput(self, obj):
        return obj.netoutput if self._detail() else None
