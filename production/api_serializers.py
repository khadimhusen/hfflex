from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from rest_framework import serializers

from customer.models import Customer, Address
from material.models import Material, MatType, Grade, Unit
from itemmaster.models import Problem
from employee.models import Worker
from quality.models import QCTest
from order.models import JobProcess, JobMaterial, Job
from .models import (
    Inward, Stockdetail, ProdReport, ProdInput, ProdPerson, ProdProblem, JobQc,
    DispatchRegister, OtherDispatchItem, ProductionProblem, ProblemTag, JobMaterialStatus,
)
from .querysets import supervisor_users


# ---- lookups --------------------------------------------------------------

class SupplierLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name']


class CustomerLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name']


class AddressLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ['id', 'addname', 'add1', 'add2', 'pincode']


class WorkerLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Worker
        fields = ['id', 'worker_name', 'emp_code']


class ProblemLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Problem
        fields = ['id', 'problem']


class QcTestLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = QCTest
        fields = ['id', 'name']


class ProductionProblemLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductionProblem
        fields = ['id', 'problem']


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


class UnitLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ['id', 'unit']


class SupervisorLookupSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        return obj.get_full_name() or obj.username


class JobProcessLookupSerializer(serializers.ModelSerializer):
    """For the 'Add Production Report' flow — the JobProcess a new report
    is being added against is picked elsewhere (the job's Processes tab)
    and passed in by id, mirroring addprodreport's ?q=<jobprocess id>."""
    job_itemname = serializers.CharField(source='job.itemname', read_only=True)
    process_display = serializers.CharField(source='process.process', read_only=True)
    customer_name = serializers.CharField(source='job.joborder.customer.name', read_only=True)

    class Meta:
        model = JobProcess
        fields = ['id', 'job', 'job_itemname', 'process', 'process_display', 'customer_name', 'status', 'qty']


# ---- Stockdetail as a line item (Inward receiving, or ProdReport output) --

class StockdetailLineSerializer(serializers.ModelSerializer):
    """Shared by inward-stock/ and prod-output/ — same model, same real
    field set (InwardMaterialForm and ProdOutputAddForm both declare
    fields="__all__" on Stockdetail, but content_type/object_id are always
    supplied by the parent generic-FK context, never the user, and
    recieved/available/alloted/balance are recomputed unconditionally in
    Stockdetail.save())."""
    materialname_display = serializers.CharField(source='materialname.name', read_only=True)
    item_mat_type_display = serializers.CharField(source='item_mat_type.mat_type', read_only=True)
    item_grade_display = serializers.CharField(source='item_grade.grade', read_only=True)
    full_name = serializers.ReadOnlyField()
    used = serializers.ReadOnlyField()
    # Mirrors stocklist.html/xlviews.stocklist's "From" column -- only
    # ever populated for prodreport-sourced rolls (an inward receipt has
    # no upstream job to name), and used to link to the record that
    # actually created this roll.
    source_kind = serializers.SerializerMethodField()
    source_display = serializers.SerializerMethodField()

    class Meta:
        model = Stockdetail
        fields = [
            'id', 'materialname', 'materialname_display', 'item_mat_type', 'item_mat_type_display',
            'item_grade', 'item_grade_display', 'full_name', 'size', 'micron', 'gsm', 'rate', 'qc_status',
            'remark', 'gross_wt', 'tare_wt', 'recieved', 'used', 'available', 'alloted', 'balance', 'nos',
            'content_type', 'object_id', 'source_kind', 'source_display', 'created', 'createdby', 'edited', 'editedby',
        ]
        read_only_fields = [
            'recieved', 'available', 'alloted', 'balance',
            'content_type', 'object_id', 'created', 'createdby', 'edited', 'editedby',
        ]

    def get_source_kind(self, obj):
        return obj.content_type.model if obj.content_type_id else None

    def get_source_display(self, obj):
        if obj.content_type_id and obj.content_type.model == 'prodreport':
            report = obj.content_object
            if report:
                return str(report.prodprocess.job)
        return ''

    def validate(self, attrs):
        # Same class of check as ProdInput's returned<=grossinput: the old
        # app never enforced this either (Stockdetail.save() would happily
        # compute a negative recieved), but a tare weight heavier than the
        # gross weight makes no physical sense.
        gross_wt = attrs.get('gross_wt', getattr(self.instance, 'gross_wt', None))
        tare_wt = attrs.get('tare_wt', getattr(self.instance, 'tare_wt', None))
        if gross_wt is not None and tare_wt is not None and tare_wt > gross_wt:
            raise serializers.ValidationError({'tare_wt': ['Tare Wt cannot be greater than Gross Wt.']})
        return attrs


# ---- Inward -----------------------------------------------------------

class InwardStockNestedSerializer(StockdetailLineSerializer):
    """StockdetailLineSerializer's 'id' is read-only (auto PK), which is
    right for the standalone inward-stock/ endpoint but wrong here: the
    nested 'stock' list on InwardSerializer needs a writable id to tell an
    edited existing line apart from a newly added one (see
    InwardSerializer.update)."""
    id = serializers.IntegerField(required=False)


class InwardSerializer(serializers.ModelSerializer):
    """Edited as a single form, like QuotationSerializer -- but unlike
    QuotationItem, a Stockdetail line can already be PROTECTed by
    ProdInput/JobMaterialStatus/dispatch once consumed downstream, so
    update() below matches existing lines by id and updates them in place
    instead of deleting and recreating the whole set."""
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)
    stock_count = serializers.IntegerField(source='stock.count', read_only=True)
    stock = InwardStockNestedSerializer(many=True, required=False)

    class Meta:
        model = Inward
        fields = [
            'id', 'docdate', 'supplier', 'supplier_name', 'inwarddate', 'invoice', 'stock_count', 'stock',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']

    @transaction.atomic
    def create(self, validated_data):
        # 'createdby' arrives already merged into validated_data (the
        # viewset's perform_create calls serializer.save(createdby=...)) --
        # only the nested stock lines need it set explicitly here.
        stock_data = validated_data.pop('stock', [])
        request = self.context.get('request')
        user = request.user if request else None

        inward = Inward.objects.create(**validated_data)
        for item in stock_data:
            item.pop('id', None)
            inward.stock.create(**item, createdby=user)
        return inward

    @transaction.atomic
    def update(self, instance, validated_data):
        # Likewise 'editedby' is already in validated_data via
        # perform_update's serializer.save(editedby=...).
        # Wrapped in one transaction: a ProtectedError on the final delete
        # (or any other failure) must not leave the other lines' updates
        # applied while the request as a whole reports failure.
        stock_data = validated_data.pop('stock', None)
        request = self.context.get('request')
        user = request.user if request else None

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if stock_data is not None:
            existing = {s.id: s for s in instance.stock.all()}
            kept_ids = set()
            for item in stock_data:
                item_id = item.pop('id', None)
                if item_id and item_id in existing:
                    kept_ids.add(item_id)
                    line = existing[item_id]
                    for attr, value in item.items():
                        setattr(line, attr, value)
                    if user:
                        line.editedby = user
                    line.save()
                else:
                    inward_stock = instance.stock.create(**item, createdby=user)
                    kept_ids.add(inward_stock.id)

            removed_ids = set(existing) - kept_ids
            if removed_ids:
                try:
                    with transaction.atomic():
                        instance.stock.filter(id__in=removed_ids).delete()
                except ProtectedError:
                    raise serializers.ValidationError({
                        'stock': [
                            'One or more removed lines are already in use '
                            '(allotted, consumed, or dispatched) and cannot be deleted.',
                        ],
                    })

        return instance


# ---- ProdReport and its sub-resources --------------------------------

class ProdReportSerializer(serializers.ModelSerializer):
    """Mirrors NewProdReportForm (create: processdate/qty/unit/totalkg/
    supervisor) and ProdReportForm (edit: everything except prodprocess —
    same field-writability split as Job/JobDetailEditForm)."""
    job_itemname = serializers.CharField(source='prodprocess.job.itemname', read_only=True)
    job_id = serializers.IntegerField(source='prodprocess.job_id', read_only=True)
    process_display = serializers.CharField(source='prodprocess.process.process', read_only=True)
    process_status = serializers.CharField(source='prodprocess.status', read_only=True)
    unit_display = serializers.CharField(source='unit.unit', read_only=True, default=None)
    supervisor_name = serializers.CharField(source='supervisor.get_full_name', read_only=True, default=None)
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)

    grossinput = serializers.ReadOnlyField()
    totalbalance = serializers.ReadOnlyField()
    totalinput = serializers.ReadOnlyField()
    totalwtgain = serializers.ReadOnlyField()
    grossoutput = serializers.ReadOnlyField()
    netoutput = serializers.ReadOnlyField()
    grosstarewt = serializers.ReadOnlyField()
    grossrecieved = serializers.ReadOnlyField()
    grossnos = serializers.ReadOnlyField()
    wastepercentage = serializers.ReadOnlyField()
    wasteoutput = serializers.ReadOnlyField()
    wasteoutputpercentage = serializers.ReadOnlyField()
    massbalancediff = serializers.ReadOnlyField()
    massbalanceerrorpercentage = serializers.ReadOnlyField()

    class Meta:
        model = ProdReport
        fields = [
            'id', 'prodprocess', 'job_id', 'job_itemname', 'process_display', 'process_status',
            'processdate', 'qty', 'unit', 'unit_display', 'totalkg', 'checked', 'approved', 'remark',
            'supervisor', 'supervisor_name',
            'grossinput', 'totalbalance', 'totalinput', 'totalwtgain', 'grossoutput', 'netoutput',
            'grosstarewt', 'grossrecieved', 'grossnos', 'wastepercentage',
            'wasteoutput', 'wasteoutputpercentage', 'massbalancediff', 'massbalanceerrorpercentage',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supervisor'].queryset = supervisor_users()
        if self.instance is not None:
            # prodprocess is set once at creation (addprodreport) and never
            # editable after — matches ProdReportForm's exclude=['prodprocess'].
            self.fields['prodprocess'].read_only = True


class ProdInputSerializer(serializers.ModelSerializer):
    material_display = serializers.CharField(source='material.full_name', read_only=True)
    material_available = serializers.DecimalField(
        source='material.available', read_only=True, max_digits=10, decimal_places=3, default=None,
    )
    prodreport_display = serializers.CharField(source='prodreport.prodprocess', read_only=True, default=None)

    class Meta:
        model = ProdInput
        fields = [
            'id', 'prodreport', 'prodreport_display', 'material', 'material_display', 'material_available',
            'grossinput', 'returned', 'inputqty', 'wtgain',
            'created', 'createdby', 'edited', 'editedby',
        ]
        read_only_fields = [
            # ProdInput.save() unconditionally recomputes wtgain from
            # material.materialname.solid * inputqty / 100.
            'wtgain', 'created', 'createdby', 'edited', 'editedby',
        ]

    def validate(self, attrs):
        grossinput = attrs.get('grossinput', getattr(self.instance, 'grossinput', None))
        returned = attrs.get('returned', getattr(self.instance, 'returned', None))
        if grossinput is not None and returned is not None and returned > grossinput:
            raise serializers.ValidationError({'returned': ['Returned cannot be greater than Gross Input.']})
        return attrs


class JobMaterialStatusSerializer(serializers.ModelSerializer):
    """Read-only -- mirrors singlematerailedit.html's "Material Alloted
    Detail" table (one row per job a stock roll was allocated to). Actually
    editing an allocation stays on the job material page (jobmaterialstatusedit
    in the old app), this is just for display/linking from the stock side."""
    job_id = serializers.IntegerField(source='jobmaterial.job_id', read_only=True)
    job_display = serializers.CharField(source='jobmaterial.job', read_only=True)

    class Meta:
        model = JobMaterialStatus
        fields = ['id', 'jobmaterial', 'job_id', 'job_display', 'allote', 'qty', 'created']
        read_only_fields = fields


class ProdPersonSerializer(serializers.ModelSerializer):
    person_display = serializers.CharField(source='person.worker_name', read_only=True)

    class Meta:
        model = ProdPerson
        fields = ['id', 'prodreport', 'person', 'person_display']


class ProdProblemSerializer(serializers.ModelSerializer):
    problem_display = serializers.CharField(source='problem.problem', read_only=True)

    class Meta:
        model = ProdProblem
        fields = ['id', 'prodreport', 'problem', 'problem_display', 'timewaste', 'action']


class JobQcSerializer(serializers.ModelSerializer):
    qctest_display = serializers.CharField(source='qctest.name', read_only=True)
    prodreport_display = serializers.CharField(source='prodreport.__str__', read_only=True)
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)

    class Meta:
        model = JobQc
        fields = [
            'id', 'prodreport', 'prodreport_display', 'qctest', 'qctest_display', 'result', 'lock',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']


class ProblemTagSerializer(serializers.ModelSerializer):
    tagname_display = serializers.CharField(source='tagname.problem', read_only=True)

    class Meta:
        model = ProblemTag
        fields = [
            'id', 'outputroll', 'tagname', 'tagname_display',
            'created', 'createdby', 'edited', 'editedby',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']


# ---- Dispatch -----------------------------------------------------------

class OtherDispatchItemSerializer(serializers.ModelSerializer):
    unit_display = serializers.CharField(source='unit.unit', read_only=True, default=None)

    class Meta:
        model = OtherDispatchItem
        fields = ['id', 'dispatch', 'item_detail', 'qty', 'unit', 'unit_display', 'approxvalue']


class DispatchRegisterSerializer(serializers.ModelSerializer):
    """Mirrors DispatchNewForm (create: everything except dispatch_material/
    createdby/editedby) and DispatchForm (edit: adds dispatch_material,
    excludes only createdby/editedby/lock)."""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    address_display = serializers.CharField(source='address.addname', read_only=True, default=None)
    totalsum = serializers.ReadOnlyField()
    created_by_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)

    class Meta:
        model = DispatchRegister
        fields = [
            'id', 'customer', 'customer_name', 'dispatch_material', 'dispatchdate', 'address',
            'address_display', 'value', 'recievedby', 'contact', 'recieptnumber', 'transport', 'person',
            'vehicle', 'remark', 'imagename1', 'imagename2', 'lock', 'totalsum',
            'created', 'createdby', 'created_by_name', 'edited', 'editedby',
        ]
        read_only_fields = ['lock', 'created', 'createdby', 'edited', 'editedby']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is None:
            # DispatchNewForm (create) never touches dispatch_material —
            # materials are only attached once editing an existing dispatch.
            self.fields['dispatch_material'].required = False
        elif getattr(self.instance, 'lock', False):
            # Mirrors dispatchdetailedit exactly: dispatch_form.save_m2m()
            # (which is what actually persists dispatch_material) only
            # runs when not locked — every other field still saves.
            # getattr (not a direct .lock access): DRF's many_init briefly
            # constructs a "child" instance of this serializer with the
            # whole list/queryset as self.instance before wrapping it in a
            # ListSerializer — a plain attribute access would crash there.
            self.fields['dispatch_material'].read_only = True


class DispatchableStockSerializer(serializers.ModelSerializer):
    """A finished-goods Stockdetail row eligible to go into a dispatch —
    mirrors DispatchForm's dispatch_material queryset/label_from_instance."""
    label = serializers.SerializerMethodField()
    job_id = serializers.SerializerMethodField()
    # Same as label but without the per-roll "Gross Wt." suffix -- one
    # dispatch can carry finished rolls from several different jobs, so
    # the frontend groups attached rolls by job_id under this as the
    # group header, same idea as Inward's material-spec group headers.
    job_display = serializers.SerializerMethodField()

    class Meta:
        model = Stockdetail
        fields = ['id', 'label', 'job_id', 'job_display', 'gross_wt', 'tare_wt', 'recieved', 'nos']

    def _report(self, obj):
        return obj.content_object

    def get_label(self, obj):
        report = self._report(obj)
        if not report:
            return obj.full_name
        job = report.prodprocess.job
        return f'{job.rate}/{job.unit}-{job.itemname}= Gross Wt. {obj.gross_wt}'

    def get_job_id(self, obj):
        report = self._report(obj)
        return report.prodprocess.job_id if report else None

    def get_job_display(self, obj):
        report = self._report(obj)
        if not report:
            return obj.full_name
        job = report.prodprocess.job
        return f'{job.rate}/{job.unit}-{job.itemname}'


class DispatchApprovalSerializer(serializers.ModelSerializer):
    """Mirrors DispatchApprovalForm exactly: invoice becomes required when
    the job's prejob carries a new cylinder charge or design charge."""

    class Meta:
        model = Job
        fields = ['dispatch_approval', 'dispatch_remark', 'invoice']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance') or getattr(self, 'instance', None)
        prejob = getattr(instance, 'prejob', None) if instance else None
        if prejob and ((prejob.new_cyl_qty or 0) > 1 or (prejob.design_charges or 0) > 1):
            self.fields['invoice'].required = True
