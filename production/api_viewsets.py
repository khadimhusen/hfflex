import datetime

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q, Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from customer.models import Customer, Address
from material.models import Material, MatType, Grade, Unit
from itemmaster.models import Problem
from employee.models import Worker
from quality.models import QCTest
from order.models import JobProcess, Job
from .models import (
    Inward, Stockdetail, ProdReport, ProdInput, ProdPerson, ProdProblem, JobQc,
    DispatchRegister, OtherDispatchItem, ProductionProblem, ProblemTag,
)
from .api_serializers import (
    SupplierLookupSerializer, CustomerLookupSerializer, AddressLookupSerializer, WorkerLookupSerializer,
    ProblemLookupSerializer, QcTestLookupSerializer, ProductionProblemLookupSerializer,
    MaterialLookupSerializer, MatTypeLookupSerializer, GradeLookupSerializer, UnitLookupSerializer,
    SupervisorLookupSerializer, JobProcessLookupSerializer,
    StockdetailLineSerializer, InwardSerializer,
    ProdReportSerializer, ProdInputSerializer, ProdPersonSerializer, ProdProblemSerializer, JobQcSerializer,
    ProblemTagSerializer, OtherDispatchItemSerializer, DispatchRegisterSerializer, DispatchableStockSerializer,
    DispatchApprovalSerializer,
)
from .permissions import IsProductionUser, IsProductionReportUser, IsStockUser, IsDispatchUser
from .querysets import supervisor_users
from .filters import ProdReportFilter, StockFilter, DispatchFilter, InwardFilter


# ---- shared lookups -------------------------------------------------------

class SupplierLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Customer.objects.filter(is_supplier=True).order_by('name')
    serializer_class = SupplierLookupSerializer
    permission_classes = [IsStockUser]
    search_fields = ['name']


class CustomerLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Customer.objects.filter(active=True).order_by('name')
    serializer_class = CustomerLookupSerializer
    permission_classes = [IsDispatchUser]
    search_fields = ['name']


class AddressLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Address.objects.all().order_by('addname')
    serializer_class = AddressLookupSerializer
    permission_classes = [IsDispatchUser]
    filterset_fields = ['customer']


class WorkerLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Worker.objects.filter(is_active=True).order_by('worker_name')
    serializer_class = WorkerLookupSerializer
    permission_classes = [IsProductionReportUser]


class ProblemLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Problem.objects.filter(is_active=True).order_by('problem')
    serializer_class = ProblemLookupSerializer
    permission_classes = [IsProductionReportUser]


class QcTestLookupViewSet(viewsets.ReadOnlyModelViewSet):
    """?prodreport=<id> mirrors AddJobQcForm's exact scoping: only the
    QCTests registered against this report's own process."""
    serializer_class = QcTestLookupSerializer
    permission_classes = [IsProductionReportUser]

    def get_queryset(self):
        prodreport_id = self.request.query_params.get('prodreport')
        if not prodreport_id:
            return QCTest.objects.none()
        report = ProdReport.objects.filter(id=prodreport_id).select_related('prodprocess__process').first()
        if not report:
            return QCTest.objects.none()
        return report.prodprocess.process.qctest_set.order_by('name')


class ProductionProblemLookupViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductionProblemLookupSerializer
    permission_classes = [IsProductionReportUser]
    filterset_fields = ['process']

    def get_queryset(self):
        return ProductionProblem.objects.order_by('problem')


class MaterialLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Material.objects.order_by('name')
    serializer_class = MaterialLookupSerializer
    permission_classes = [IsProductionUser]


class MatTypeLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MatType.objects.order_by('mat_type')
    serializer_class = MatTypeLookupSerializer
    permission_classes = [IsProductionUser]


class GradeLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Grade.objects.order_by('grade')
    serializer_class = GradeLookupSerializer
    permission_classes = [IsProductionUser]


class UnitLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Unit.objects.order_by('unit')
    serializer_class = UnitLookupSerializer
    permission_classes = [IsProductionUser]


class SupervisorLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = supervisor_users().order_by('first_name', 'last_name')
    serializer_class = SupervisorLookupSerializer
    permission_classes = [IsProductionReportUser]


class JobProcessLookupViewSet(viewsets.ReadOnlyModelViewSet):
    """Look up a single JobProcess by id — the 'Add Production Report'
    flow is entered from the job's Processes tab with the process already
    chosen, mirroring addprodreport's ?q=<jobprocess id>."""
    queryset = JobProcess.objects.select_related('job', 'job__joborder__customer', 'process')
    serializer_class = JobProcessLookupSerializer
    permission_classes = [IsProductionReportUser]


class ProdInputMaterialLookupViewSet(viewsets.ReadOnlyModelViewSet):
    """?prodreport=<id> mirrors ProdInputBlankForm's exact process-specific
    matching: materials already allotted to this job (JobMaterialStatus),
    or already produced as output by an earlier process of the same job,
    plus a process-specific catalyst/solvent/packing top-up lot (Toluene/
    Ethyl for Printing, Ethyl for Lamination, Packing for Slitting/
    Pouching) — all filtered to balance>0, qc_status Ok."""
    serializer_class = StockdetailLineSerializer
    permission_classes = [IsProductionReportUser]

    def get_queryset(self):
        prodreport_id = self.request.query_params.get('prodreport')
        if not prodreport_id:
            return Stockdetail.objects.none()
        report = ProdReport.objects.filter(id=prodreport_id).select_related(
            'prodprocess__job', 'prodprocess__process',
        ).first()
        if not report:
            return Stockdetail.objects.none()

        from production.models import JobMaterialStatus
        job = report.prodprocess.job
        allotted_ids = JobMaterialStatus.objects.filter(jobmaterial__job=job).values_list('allote_id', flat=True)
        job_report_ids = ProdReport.objects.filter(prodprocess__job=job).values_list('id', flat=True)

        qs = Stockdetail.objects.filter(id__in=allotted_ids, balance__gt=0, qc_status='Ok') | Stockdetail.objects.filter(
            prodreports__in=job_report_ids, balance__gt=0, qc_status='Ok',
        )

        process_name = report.prodprocess.process.process
        topup_names = {
            'Printing': ['TOLUENE', 'ETHYL'],
            'Lamination': ['ETHYL'],
            'Slitting': ['PACKING'],
            'Pouching': ['PACKING'],
        }.get(process_name, [])
        for name in topup_names:
            qs = qs | Stockdetail.objects.filter(balance__gt=0, qc_status='Ok', materialname__name=name)[:1]

        return qs.order_by('materialname', 'size')


# ---- Inward -------------------------------------------------------------

class InwardViewSet(viewsets.ModelViewSet):
    # No delete view ever existed in the old app for this model either.
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    queryset = Inward.objects.select_related('supplier', 'createdby', 'editedby')
    serializer_class = InwardSerializer
    permission_classes = [IsStockUser]
    filterset_class = InwardFilter

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)


class InwardStockViewSet(viewsets.ModelViewSet):
    """The physical stock lines received on an Inward — filter with
    ?inward=<id>. content_type/object_id are stamped server-side, mirroring
    generic_inlineformset_factory(Stockdetail, ...) always tying new rows
    to the parent instance."""
    serializer_class = StockdetailLineSerializer
    permission_classes = [IsStockUser]

    def get_queryset(self):
        ct = ContentType.objects.get_for_model(Inward)
        qs = Stockdetail.objects.filter(content_type=ct).select_related(
            'materialname', 'item_mat_type', 'item_grade',
        )
        inward_id = self.request.query_params.get('inward')
        if inward_id:
            qs = qs.filter(object_id=inward_id)
        return qs.order_by('id')

    def perform_create(self, serializer):
        inward_id = self.request.data.get('inward')
        inward = Inward.objects.filter(id=inward_id).first() if inward_id else None
        if not inward:
            raise ValidationError({'inward': ['This field is required.']})
        ct = ContentType.objects.get_for_model(Inward)
        serializer.save(content_type=ct, object_id=inward.id, createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)


# ---- ProdReport and its sub-resources ------------------------------------

class ProdReportViewSet(viewsets.ModelViewSet):
    # No delete — matches every other report/job-adjacent viewset in this
    # codebase; the old app never exposed one either.
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    queryset = ProdReport.objects.select_related(
        'prodprocess', 'prodprocess__job', 'prodprocess__job__joborder__customer', 'prodprocess__process',
        'unit', 'supervisor', 'createdby', 'editedby',
    )
    serializer_class = ProdReportSerializer
    permission_classes = [IsProductionReportUser]
    filterset_class = ProdReportFilter

    def perform_create(self, serializer):
        # Mirrors addprodreport: the JobProcess is picked on the job's
        # Processes tab first (old app's ?q=<jobprocess id>), then
        # submitted as a normal field — prodprocess is writable on create,
        # then locked (see the serializer's __init__), same asymmetry as
        # Job.itemmaster/.prejob.
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)
        process_status = self.request.data.get('process_status')
        if process_status:
            # Mutate the already-loaded prodprocess object (not a bulk
            # .update()) so the response's process_status field — sourced
            # from this same cached relation — reflects the change
            # immediately instead of the pre-update value.
            jobprocess = serializer.instance.prodprocess
            jobprocess.status = process_status
            jobprocess.save(update_fields=['status'])


class ProdInputViewSet(viewsets.ModelViewSet):
    queryset = ProdInput.objects.select_related(
        'material', 'material__materialname', 'prodreport', 'createdby', 'editedby',
    ).order_by('id')
    serializer_class = ProdInputSerializer
    permission_classes = [IsProductionReportUser]
    filterset_fields = ['prodreport']

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)


class ProdOutputViewSet(viewsets.ModelViewSet):
    """The finished/produced Stockdetail rows tied to a ProdReport — filter
    with ?prodreport=<id>. Mirrors prodreportaddoutput/addoutputhtmx."""
    serializer_class = StockdetailLineSerializer
    permission_classes = [IsProductionReportUser]

    def get_queryset(self):
        ct = ContentType.objects.get_for_model(ProdReport)
        qs = Stockdetail.objects.filter(content_type=ct).select_related(
            'materialname', 'item_mat_type', 'item_grade',
        )
        prodreport_id = self.request.query_params.get('prodreport')
        if prodreport_id:
            qs = qs.filter(object_id=prodreport_id)
        return qs.order_by('id')

    def perform_create(self, serializer):
        prodreport_id = self.request.data.get('prodreport')
        report = ProdReport.objects.filter(id=prodreport_id).first() if prodreport_id else None
        if not report:
            raise ValidationError({'prodreport': ['This field is required.']})
        ct = ContentType.objects.get_for_model(ProdReport)
        serializer.save(content_type=ct, object_id=report.id, createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)


class ProdPersonViewSet(viewsets.ModelViewSet):
    queryset = ProdPerson.objects.select_related('person', 'prodreport').order_by('id')
    serializer_class = ProdPersonSerializer
    permission_classes = [IsProductionReportUser]
    filterset_fields = ['prodreport']


class ProdProblemViewSet(viewsets.ModelViewSet):
    queryset = ProdProblem.objects.select_related('problem', 'prodreport').order_by('id')
    serializer_class = ProdProblemSerializer
    permission_classes = [IsProductionReportUser]
    filterset_fields = ['prodreport']


class JobQcViewSet(viewsets.ModelViewSet):
    queryset = JobQc.objects.select_related('qctest', 'prodreport', 'createdby', 'editedby')
    serializer_class = JobQcSerializer
    permission_classes = [IsProductionReportUser]
    filterset_fields = ['prodreport']

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)


# ---- Stock ----------------------------------------------------------------

class StockdetailReportViewSet(viewsets.ReadOnlyModelViewSet):
    """Mirrors stocklist.html — a filtered, read-only report over every
    Stockdetail row regardless of source (inward/prodreport)."""
    queryset = Stockdetail.objects.select_related(
        'materialname', 'item_mat_type', 'item_grade', 'content_type',
    ).annotate(allote=Sum('jobmaterialstatus__qty', distinct=True)).order_by('-id')
    serializer_class = StockdetailLineSerializer
    permission_classes = [IsStockUser]
    filterset_class = StockFilter

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        qs = self.filter_queryset(self.get_queryset())
        totals = qs.aggregate(total_balance=Sum('balance'), total_available=Sum('available'))
        response.data['total_balance'] = totals['total_balance'] or 0
        response.data['total_available'] = totals['total_available'] or 0
        return response


class StockdetailEditViewSet(viewsets.ModelViewSet):
    """Mirrors singlematerailedit — the only thing editable from the stock
    report is qc_status/remark on an existing lot."""
    http_method_names = ['get', 'patch', 'head', 'options']
    queryset = Stockdetail.objects.select_related('materialname', 'item_mat_type', 'item_grade')
    serializer_class = StockdetailLineSerializer
    permission_classes = [IsStockUser]

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)


class ProblemTagViewSet(viewsets.ModelViewSet):
    """Tags on a finished output roll — filter with ?outputroll=<id>,
    mirrors prodreporteditoutput's ProblemTag inline formset."""
    queryset = ProblemTag.objects.select_related('outputroll', 'tagname').order_by('-id')
    serializer_class = ProblemTagSerializer
    permission_classes = [IsStockUser]
    filterset_fields = ['outputroll']

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)


# ---- Dispatch ---------------------------------------------------------

class DispatchRegisterViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    queryset = DispatchRegister.objects.select_related('customer', 'address', 'createdby', 'editedby')
    serializer_class = DispatchRegisterSerializer
    permission_classes = [IsDispatchUser]
    filterset_class = DispatchFilter

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)

    @action(detail=True, methods=['post'])
    def lock(self, request, pk=None):
        DispatchRegister.objects.filter(id=pk).update(lock=True)
        return Response({'lock': True})

    @action(detail=True, methods=['post'])
    def unlock(self, request, pk=None):
        DispatchRegister.objects.filter(id=pk).update(lock=False)
        return Response({'lock': False})


class OtherDispatchItemViewSet(viewsets.ModelViewSet):
    queryset = OtherDispatchItem.objects.select_related('dispatch', 'unit').order_by('id')
    serializer_class = OtherDispatchItemSerializer
    permission_classes = [IsDispatchUser]
    filterset_fields = ['dispatch']


class DispatchableStockViewSet(viewsets.ReadOnlyModelViewSet):
    """Finished-goods stock still awaiting dispatch for a customer — mirrors
    DispatchForm's dispatch_material queryset. ?customer=<id> required."""
    serializer_class = DispatchableStockSerializer
    permission_classes = [IsDispatchUser]

    def get_queryset(self):
        customer_id = self.request.query_params.get('customer')
        if not customer_id:
            return Stockdetail.objects.none()
        return Stockdetail.objects.filter(
            prodreports__prodprocess__job__joborder__customer__id=customer_id, dispached__isnull=True,
            qc_status='Finished', prodreports__prodprocess__job__dispatch_approval=True,
            prodreports__checked=True, prodreports__approved=True,
        ).prefetch_related('content_object__prodprocess__job').order_by('id')


class DispatchPendingView(APIView):
    """Mirrors dispatchpending — finished goods approved for dispatch,
    grouped by customer then job."""
    permission_classes = [IsDispatchUser]

    def get(self, request):
        material_list = Stockdetail.objects.filter(
            dispached__isnull=True, qc_status='Finished', recieved__gt=0.001,
            prodreports__prodprocess__job__dispatch_approval=True,
        ).prefetch_related(
            'content_object__prodprocess__job__joborder__customer',
        ).order_by('id')

        data = {}
        for material in material_list:
            report = material.content_object
            job = report.prodprocess.job
            cust = job.joborder.customer.name
            bucket = data.setdefault(cust, {})
            entry = bucket.setdefault(job.id, {
                'job_id': job.id, 'job_itemname': job.itemname, 'qty': 0, 'nos': 0,
                'po': job.joborder.po, 'orderqty': job.kgqty, 'remark': job.dispatch_remark,
            })
            entry['qty'] = float(entry['qty']) + float(material.recieved or 0)
            entry['nos'] = float(entry['nos']) + float(material.nos or 0)

        return Response([
            {'customer': cust, 'jobs': list(jobs.values())} for cust, jobs in sorted(data.items())
        ])


class DispatchApprovalPendingView(APIView):
    """Mirrors dispatchapprovalpending — finished, completed/partially-ready
    jobs not yet approved for dispatch, grouped by customer then job."""
    permission_classes = [IsDispatchUser]

    def get(self, request):
        material_list = Stockdetail.objects.filter(
            dispached__isnull=True, qc_status='Finished', recieved__gt=0.001,
            prodreports__prodprocess__job__dispatch_approval=False,
            prodreports__prodprocess__job__jobstatus__in=['Completed', 'Partially Ready'],
        ).prefetch_related(
            'content_object__prodprocess__job__joborder__customer',
            'content_object__prodprocess__job__prejob',
        ).order_by('id')

        data = {}
        for material in material_list:
            report = material.content_object
            job = report.prodprocess.job
            prejob = job.prejob
            cust = job.joborder.customer.name
            bucket = data.setdefault(cust, {})
            entry = bucket.setdefault(job.id, {
                'job_id': job.id, 'job_itemname': job.itemname, 'qty': 0, 'orderqty': job.kgqty,
                'rate': job.rate, 'unit_display': job.unit.unit if job.unit else None,
                'new_cyl_qty': prejob.new_cyl_qty if prejob else None,
                'cyl_cost': prejob.cyl_cost if prejob else None,
                'design_charges': prejob.design_charges if prejob else None,
                'invoice_required': bool(
                    prejob and ((prejob.new_cyl_qty or 0) > 1 or (prejob.design_charges or 0) > 1)
                ),
            })
            entry['qty'] = float(entry['qty']) + float(material.recieved or 0)

        return Response([
            {'customer': cust, 'jobs': list(jobs.values())} for cust, jobs in sorted(data.items())
        ])


class DispatchApprovalView(APIView):
    """Mirrors dispatchapproval: approves (or edits the approval remark on)
    a single job from the approval-pending list."""
    permission_classes = [IsDispatchUser]

    def post(self, request, pk=None):
        job = Job.objects.filter(id=pk).select_related('prejob').first()
        if not job:
            raise ValidationError({'detail': ['Job not found.']})
        serializer = DispatchApprovalSerializer(job, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        job = serializer.save(dispatch_approval_date=datetime.datetime.now())
        return Response({
            'id': job.id, 'dispatch_approval': job.dispatch_approval,
            'dispatch_approval_date': job.dispatch_approval_date, 'dispatch_remark': job.dispatch_remark,
            'invoice': job.invoice,
        })
