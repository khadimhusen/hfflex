from django.contrib.auth.models import User
from rest_framework import serializers

from customer.models import Customer, Address
from material.models import Unit, Material, MatType, Grade
from itemmaster.models import ItemMaster, Process, Color, AttributeMaster, StdParameter, PouchType, LamiRubber
from preorder.models import JobName
from production.models import Stockdetail, JobMaterialStatus
from myproject.thumbnails import get_or_create_thumbnail
from .models import Order, Job, JobMaterial, JobProcess, JobColor, JobImage, JobItemAttribute, JobCoa, JobChangeLog
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
    are final-submitted and not yet converted into a Job. Carries qty/unit/
    rate/remark too (not just the label fields) so the frontend can prefill
    the rest of the Add Job form from a single lookup call instead of a
    second round trip once a prejob is picked."""
    unit_display = serializers.CharField(source='unit.unit', read_only=True)
    preorder_customer = serializers.CharField(source='preorder.customer', read_only=True)

    class Meta:
        model = JobName
        fields = [
            'id', 'jobname', 'qty', 'unit', 'unit_display', 'rate', 'remark', 'new_cylinder', 'new_cyl_qty',
            'preorder_customer',
        ]


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
    schedule_date = serializers.DateTimeField(source='joborder.deliverydate', read_only=True, default=None)
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
    threeweek = serializers.SerializerMethodField()
    fourweek = serializers.SerializerMethodField()

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
            'id', 'prejob', 'joborder', 'order_customer', 'schedule_date', 'itemmaster', 'itemname_display',
            'quantity', 'unit', 'unit_display', 'rate', 'waste', 'jobstatus',
            'account_clearance_date', 'approvedby', 'approvedby_name',
            'marketing_person', 'marketing_person_name',
            'dispatch_approval', 'dispatch_approval_date', 'dispatch_remark', 'jobremark',
            'kgqty', 'itemname', 'invoice', 'barcode', 'packsize',
            'replength', 'openwidth', 'slit_size', 'no_of_repeat', 'no_of_ups',
            'cyl_length', 'cyl_circum', 'printing', 'total_gsm', 'pouch_weight', 'pouch_per_kg',
            'pouch_type', 'supply_form', 'film_size', 'remark', 'unwind_direction', 'lami_rubber',
            'totalpouch', 'totalmeter', 'job_waste', 'job_repeat_status', 'calculated_waste_percentage',
            'ply', 'pouchqty', 'kgrate', 'late', 'nearschedule', 'oneweek', 'twoweek', 'threeweek', 'fourweek',
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

    def get_threeweek(self, obj):
        return bool(obj.joborder.deliverydate) and obj.threeweek

    def get_fourweek(self, obj):
        return bool(obj.joborder.deliverydate) and obj.fourweek

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


# ---- Job sub-resource lookups -------------------------------------------

class MaterialLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = ['id', 'name']


class MatTypeLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = MatType
        fields = ['id', 'mat_type']


class GradeLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grade
        fields = ['id', 'grade']


class ProcessLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Process
        fields = ['id', 'process']


class ColorLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Color
        fields = ['id', 'colorname', 'pantonecolor', 'hexcode']


class AttributeMasterLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttributeMaster
        fields = ['id', 'attribute']


class StdParameterLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = StdParameter
        fields = ['id', 'parameter', 'unit_of_measure']


class PouchTypeLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = PouchType
        fields = ['id', 'pouchtype']


class LamiRubberLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = LamiRubber
        fields = ['id', 'rubber', 'status']


# ---- Job sub-resources ---------------------------------------------------

class JobMaterialSerializer(serializers.ModelSerializer):
    materialname_display = serializers.CharField(source='materialname.name', read_only=True)
    item_mat_type_display = serializers.CharField(source='item_mat_type.mat_type', read_only=True)
    item_grade_display = serializers.CharField(source='item_grade.grade', read_only=True)
    avail = serializers.ReadOnlyField()
    required = serializers.ReadOnlyField()
    mat_length = serializers.ReadOnlyField()
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)

    class Meta:
        model = JobMaterial
        fields = [
            'id', 'job', 'materialname', 'materialname_display', 'item_mat_type', 'item_mat_type_display',
            'item_grade', 'item_grade_display', 'size', 'micron', 'gsm', 'req', 'available', 'to_order',
            'orderedqty', 'receivedqty', 'po', 'length', 'avail', 'required', 'mat_length',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby',
        ]
        read_only_fields = [
            # JobMaterial.save() unconditionally recomputes all four of
            # these from the other fields on every save — submitting a
            # value for them is silently discarded.
            'gsm', 'length', 'available', 'to_order',
            'created', 'createdby', 'edited', 'editedby',
        ]


class JobProcessSerializer(serializers.ModelSerializer):
    process_display = serializers.CharField(source='process.process', read_only=True)
    unit_display = serializers.CharField(source='unit.unit', read_only=True, default=None)
    pendingqty = serializers.ReadOnlyField()
    produced_qty = serializers.ReadOnlyField()
    no_of_ply = serializers.ReadOnlyField()
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)

    class Meta:
        model = JobProcess
        fields = [
            'id', 'job', 'process', 'process_display', 'qty', 'unit', 'unit_display', 'status',
            'process_count', 'pendingqty', 'produced_qty', 'no_of_ply',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby',
        ]
        read_only_fields = [
            'process_count',  # set in JobProcess.save() from a count of existing rows
            'created', 'createdby', 'edited', 'editedby',
        ]


class JobColorSerializer(serializers.ModelSerializer):
    color_display = serializers.CharField(source='color.colorname', read_only=True, default=None)

    class Meta:
        model = JobColor
        fields = ['id', 'job', 'color', 'color_display', 'remark']


class JobImageSerializer(serializers.ModelSerializer):
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = JobImage
        fields = ['id', 'job', 'imagename', 'thumbnail_url', 'created', 'createdby', 'edited', 'editedby']
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']

    def get_thumbnail_url(self, obj):
        url = get_or_create_thumbnail(obj.imagename)
        if not url:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url


class JobItemAttributeSerializer(serializers.ModelSerializer):
    item_attirbuate_display = serializers.CharField(source='item_attirbuate.attribute', read_only=True)

    class Meta:
        model = JobItemAttribute
        fields = ['id', 'job', 'item_attirbuate', 'item_attirbuate_display', 'attri_value']


class JobCoaSerializer(serializers.ModelSerializer):
    standard_parameter_display = serializers.CharField(source='standard_parameter.parameter', read_only=True)
    unit_of_measure = serializers.CharField(source='standard_parameter.unit_of_measure', read_only=True)

    class Meta:
        model = JobCoa
        fields = ['id', 'job', 'standard_parameter', 'standard_parameter_display', 'unit_of_measure', 'value']


# ---- Cross-job reporting (processlist, jobmateriallist) -------------------

class ProcessReportSerializer(serializers.ModelSerializer):
    """Read-only — mirrors processlist.html exactly (a GET-filtered report
    table, no inline editing anywhere in it)."""
    process_display = serializers.CharField(source='process.process', read_only=True)
    unit_display = serializers.CharField(source='unit.unit', read_only=True, default=None)
    job_itemname = serializers.CharField(source='job.itemname', read_only=True)
    job_jobstatus = serializers.CharField(source='job.jobstatus', read_only=True)
    job_film_size = serializers.IntegerField(source='job.film_size', read_only=True)
    job_supply_form = serializers.CharField(source='job.supply_form', read_only=True)
    customer_name = serializers.CharField(source='job.joborder.customer.name', read_only=True)
    cylinder_status = serializers.CharField(source='job.itemmaster.cylinder_status', read_only=True, default=None)
    pendingqty = serializers.ReadOnlyField()
    produced_qty = serializers.ReadOnlyField()

    class Meta:
        model = JobProcess
        fields = [
            'id', 'job', 'job_itemname', 'job_jobstatus', 'job_film_size', 'job_supply_form',
            'customer_name', 'cylinder_status', 'process', 'process_display', 'qty', 'unit', 'unit_display',
            'status', 'process_count', 'pendingqty', 'produced_qty', 'created',
        ]


class JobMaterialReportSerializer(serializers.ModelSerializer):
    """Read-only — mirrors jobmaterial/list.html (a report, same as
    processlist; edits happen through the job detail page's JobMaterial
    sub-resource, not here)."""
    materialname_display = serializers.CharField(source='materialname.name', read_only=True)
    item_mat_type_display = serializers.CharField(source='item_mat_type.mat_type', read_only=True)
    item_grade_display = serializers.CharField(source='item_grade.grade', read_only=True)
    job_itemname = serializers.CharField(source='job.itemname', read_only=True)
    job_jobstatus = serializers.CharField(source='job.jobstatus', read_only=True)
    customer_name = serializers.CharField(source='job.joborder.customer.name', read_only=True)

    class Meta:
        model = JobMaterial
        fields = [
            'id', 'job', 'job_itemname', 'job_jobstatus', 'customer_name',
            'materialname', 'materialname_display', 'item_mat_type', 'item_mat_type_display',
            'item_grade', 'item_grade_display', 'size', 'micron', 'gsm', 'req', 'available',
            'to_order', 'orderedqty', 'receivedqty', 'po', 'created',
        ]


class JobChangeLogSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source='changed_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = JobChangeLog
        fields = ['id', 'job', 'field_name', 'old_value', 'new_value', 'changed_by', 'changed_by_name',
                  'changed_at', 'action']


class BulkMaterialRateSerializer(serializers.Serializer):
    """Mirrors the old `rate` view exactly: sets Stockdetail.rate for every
    matching (materialname, item_mat_type, item_grade) row that's
    currently unrated or effectively zero (<= 0.1) — a stock-wide backfill,
    not a single-row edit."""
    materialname = serializers.IntegerField()
    item_mat_type = serializers.IntegerField()
    item_grade = serializers.IntegerField()
    rate = serializers.DecimalField(max_digits=10, decimal_places=3)


class AssignMarketingPersonSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    marketing_person = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(department__department_name='marketing', is_active=True),
    )


# ---- Material allotment (JobMaterialStatus) & dispatch info ---------------

class StockdetailLookupSerializer(serializers.ModelSerializer):
    """For picking which stock lot to allot against a JobMaterial
    requirement — scoped by ?materialname=&item_mat_type=&item_grade= to
    match the requirement being fulfilled."""
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = Stockdetail
        fields = ['id', 'full_name', 'available', 'rate', 'qc_status']


class JobMaterialStatusSerializer(serializers.ModelSerializer):
    """Mirrors the old production:jobmaterialstatusedit flow — allotting a
    specific Stockdetail lot (a physical stock entry) against a
    JobMaterial's requirement. JobMaterial.avail (already exposed on
    JobMaterialSerializer) is the live sum of these rows' qty."""
    stock_display = serializers.CharField(source='allote.full_name', read_only=True)
    stock_available = serializers.DecimalField(
        source='allote.available', read_only=True, max_digits=10, decimal_places=3, default=None,
    )
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)

    class Meta:
        model = JobMaterialStatus
        fields = [
            'id', 'jobmaterial', 'allote', 'stock_display', 'stock_available', 'qty',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']


class JobDispatchItemSerializer(serializers.Serializer):
    """Mirrors jobdetail's finished_list construction exactly: one row per
    finished-goods Stockdetail entry belonging to this job (from
    Job.job_disptached), with which dispatch batch (if any) it went out
    on. dispatch_id is None for goods still pending dispatch — the old
    template grouped by this (0 meant 'Pending For Dispatch')."""
    id = serializers.IntegerField()
    object_id = serializers.IntegerField()
    gross_wt = serializers.DecimalField(max_digits=10, decimal_places=3, allow_null=True)
    tare_wt = serializers.DecimalField(max_digits=10, decimal_places=3, allow_null=True)
    recieved = serializers.DecimalField(max_digits=10, decimal_places=3, allow_null=True)
    nos = serializers.DecimalField(max_digits=10, decimal_places=0, allow_null=True)
    remark = serializers.CharField(allow_null=True)
    dispatch_id = serializers.IntegerField(allow_null=True)
    dispatch_date = serializers.DateTimeField(allow_null=True)
