from django.contrib.auth.models import User
from django.db.models import Sum, Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView

from customer.models import Customer, Address
from material.models import Unit, Material, MatType, Grade
from itemmaster.models import ItemMaster, Process, Color, AttributeMaster, StdParameter, PouchType, LamiRubber
from preorder.models import JobName
from production.models import Stockdetail, JobMaterialStatus
from .models import Order, Job, JobMaterial, JobProcess, JobColor, JobImage, JobItemAttribute, JobCoa, JobChangeLog
from .api_serializers import (
    OrderSerializer, JobSerializer, CustomerLookupSerializer, AddressLookupSerializer,
    MarketingPersonLookupSerializer, UnitLookupSerializer, ItemMasterLookupSerializer, PrejobLookupSerializer,
    MaterialLookupSerializer, MatTypeLookupSerializer, GradeLookupSerializer, ProcessLookupSerializer,
    ColorLookupSerializer, AttributeMasterLookupSerializer, StdParameterLookupSerializer,
    PouchTypeLookupSerializer, LamiRubberLookupSerializer,
    JobMaterialSerializer, JobProcessSerializer, JobColorSerializer, JobImageSerializer,
    JobItemAttributeSerializer, JobCoaSerializer,
    ProcessReportSerializer, JobMaterialReportSerializer, JobChangeLogSerializer,
    BulkMaterialRateSerializer, AssignMarketingPersonSerializer,
    StockdetailLookupSerializer, JobMaterialStatusSerializer, JobDispatchItemSerializer,
)
from .permissions import IsOrderUser
from .querysets import (
    can_edit_order, can_cancel_job, can_delete_job_subresource, can_delete_material_allotment,
)
from .filters import OrderFilter, JobFilter, JobProcessFilter, JobMaterialFilter


class CustomerLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Customer.objects.filter(active=True).order_by('name')
    serializer_class = CustomerLookupSerializer
    permission_classes = [IsOrderUser]
    search_fields = ['name']


class AddressLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Address.objects.all().order_by('addname')
    serializer_class = AddressLookupSerializer
    permission_classes = [IsOrderUser]
    filterset_fields = ['customer']


class MarketingPersonLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.filter(
        department__department_name='marketing', is_active=True,
    ).order_by('first_name', 'last_name')
    serializer_class = MarketingPersonLookupSerializer
    permission_classes = [IsOrderUser]


class UnitLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Unit.objects.order_by('unit')
    serializer_class = UnitLookupSerializer
    permission_classes = [IsOrderUser]


class ItemMasterLookupViewSet(viewsets.ReadOnlyModelViewSet):
    """For Job.itemmaster — old JobForm scoped the dropdown to
    ?itemcustomer=<order's customer>, active items only."""
    queryset = ItemMaster.objects.filter(active=True).order_by('itemname')
    serializer_class = ItemMasterLookupSerializer
    permission_classes = [IsOrderUser]
    filterset_fields = ['itemcustomer']
    search_fields = ['itemname']


class PrejobLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = JobName.objects.filter(
        job__isnull=True, preorder__final_submition=True,
    ).select_related('unit').order_by('-id')
    serializer_class = PrejobLookupSerializer
    permission_classes = [IsOrderUser]


class MaterialLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Material.objects.order_by('name')
    serializer_class = MaterialLookupSerializer
    permission_classes = [IsOrderUser]


class MatTypeLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MatType.objects.order_by('mat_type')
    serializer_class = MatTypeLookupSerializer
    permission_classes = [IsOrderUser]


class GradeLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Grade.objects.order_by('grade')
    serializer_class = GradeLookupSerializer
    permission_classes = [IsOrderUser]


class ProcessLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Process.objects.order_by('process')
    serializer_class = ProcessLookupSerializer
    permission_classes = [IsOrderUser]


class ColorLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Color.objects.order_by('colorname')
    serializer_class = ColorLookupSerializer
    permission_classes = [IsOrderUser]
    search_fields = ['colorname']


class AttributeMasterLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AttributeMaster.objects.order_by('attribute')
    serializer_class = AttributeMasterLookupSerializer
    permission_classes = [IsOrderUser]


class StdParameterLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StdParameter.objects.order_by('parameter')
    serializer_class = StdParameterLookupSerializer
    permission_classes = [IsOrderUser]


class PouchTypeLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PouchType.objects.order_by('pouchtype')
    serializer_class = PouchTypeLookupSerializer
    permission_classes = [IsOrderUser]


class LamiRubberLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LamiRubber.objects.order_by('-id')
    serializer_class = LamiRubberLookupSerializer
    permission_classes = [IsOrderUser]


class OrderViewSet(viewsets.ModelViewSet):
    # No delete view ever existed in the old app for this model either.
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    queryset = Order.objects.select_related('customer', 'delivery_at', 'createdby', 'editedby')
    serializer_class = OrderSerializer
    permission_classes = [IsOrderUser]
    filterset_class = OrderFilter

    def perform_create(self, serializer):
        marketing_person = serializer.validated_data.pop('marketing_person', None)
        order = serializer.save(createdby=self.request.user, status='Pending')
        self._sync_marketing_person(order, marketing_person)

    def perform_update(self, serializer):
        if not can_edit_order(self.request.user, serializer.instance):
            raise PermissionDenied("Only this order's creator, or a director, can change it.")
        marketing_person = serializer.validated_data.pop('marketing_person', None)
        order = serializer.save(editedby=self.request.user)
        self._sync_marketing_person(order, marketing_person)

    def _sync_marketing_person(self, order, marketing_person):
        # Mirrors orderadd/orderedit's exact side effect: submitting a
        # marketing person on the order form also updates that customer's
        # own default marketing_person, if different.
        if marketing_person and order.customer.marketing_person_id != marketing_person.id:
            order.customer.marketing_person = marketing_person
            order.customer.save(update_fields=['marketing_person'])


class JobViewSet(viewsets.ModelViewSet):
    # No delete — cancel (below) is the old app's only destructive action,
    # and even that only soft-cancels (status flip + wipes sub-resources).
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    queryset = Job.objects.select_related(
        'joborder', 'joborder__customer', 'itemmaster', 'unit', 'prejob',
        'marketing_person', 'approvedby', 'createdby', 'editedby',
    )
    serializer_class = JobSerializer
    permission_classes = [IsOrderUser]
    filterset_class = JobFilter

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['detail'] = self.action == 'retrieve'
        return context

    def perform_create(self, serializer):
        # Old app: jobs only ever get created from orderdetailedit's inline
        # formset, which is itself gated to the order's creator or a
        # director — jobdetailedit (editing an EXISTING job) has no such
        # check, so that asymmetry is intentional, not an oversight.
        joborder = serializer.validated_data['joborder']
        if not can_edit_order(self.request.user, joborder):
            raise PermissionDenied("Only this order's creator, or a director, can add jobs to it.")
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Mirrors jobdcancel exactly: directors only, wipes the job's
        material/process/color/image rows and flips status to Cancelled —
        does NOT delete the Job itself."""
        if not can_cancel_job(request.user):
            raise PermissionDenied('Only a director can cancel a job.')
        job = self.get_object()
        job.jobmaterial.all().delete()
        job.jobprocess.all().delete()
        job.jobcolors.all().delete()
        job.jobimages.all().delete()
        Job.objects.filter(id=job.id).update(jobstatus='Cancelled')
        job.refresh_from_db()
        return Response(self.get_serializer(job).data)

    @action(detail=True, methods=['post'], url_path='remove-dispatch-approval')
    def remove_dispatch_approval(self, request, pk=None):
        job = self.get_object()
        job.dispatch_approval = False
        job.dispatch_approval_date = None
        job.save()
        return Response(self.get_serializer(job).data)

    @action(detail=True, methods=['get'], url_path='dispatch-info')
    def dispatch_info(self, request, pk=None):
        """Read-only — mirrors jobdetail's finished_list exactly: one row
        per finished-goods Stockdetail belonging to this job
        (Job.job_disptached), noting which DispatchRegister batch (if any)
        it went out on. dispatch_id is None for goods still pending
        dispatch (the old template's 'Pending For Dispatch' bucket)."""
        job = self.get_object()
        rows = []
        for item in job.job_disptached.all():
            first_dispatch = item.dispached.first()
            rows.append({
                'id': item.id,
                'object_id': item.object_id,
                'gross_wt': item.gross_wt,
                'tare_wt': item.tare_wt,
                'recieved': item.recieved,
                'nos': item.nos,
                'remark': item.remark,
                'dispatch_id': first_dispatch.id if first_dispatch else None,
                'dispatch_date': first_dispatch.dispatchdate if first_dispatch else None,
            })
        rows.sort(key=lambda k: k['dispatch_id'] or 0)
        return Response(JobDispatchItemSerializer(rows, many=True).data)


class JobMaterialViewSet(viewsets.ModelViewSet):
    queryset = JobMaterial.objects.select_related(
        'job', 'job__joborder', 'materialname', 'item_mat_type', 'item_grade', 'po', 'createdby', 'editedby',
    ).order_by('id')
    serializer_class = JobMaterialSerializer
    permission_classes = [IsOrderUser]
    filterset_fields = ['job']

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)

    def perform_destroy(self, instance):
        if not can_delete_job_subresource(self.request.user, instance.job):
            raise PermissionDenied("Only this job's order creator can delete this row.")
        instance.delete()


class JobProcessViewSet(viewsets.ModelViewSet):
    queryset = JobProcess.objects.select_related(
        'job', 'job__joborder', 'process', 'unit', 'createdby', 'editedby',
    ).order_by('id')
    serializer_class = JobProcessSerializer
    permission_classes = [IsOrderUser]
    filterset_fields = ['job']

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)

    def perform_destroy(self, instance):
        if not can_delete_job_subresource(self.request.user, instance.job):
            raise PermissionDenied("Only this job's order creator can delete this row.")
        instance.delete()


class JobColorViewSet(viewsets.ModelViewSet):
    queryset = JobColor.objects.select_related('job', 'job__joborder', 'color').order_by('id')
    serializer_class = JobColorSerializer
    permission_classes = [IsOrderUser]
    filterset_fields = ['job']

    def perform_destroy(self, instance):
        if not can_delete_job_subresource(self.request.user, instance.job):
            raise PermissionDenied("Only this job's order creator can delete this row.")
        instance.delete()


class JobImageViewSet(viewsets.ModelViewSet):
    # Old app: images only ever get added/replaced via the same inline
    # formset as everything else in jobdetailedit — no dedicated delete
    # view, but the formset's can_delete flag covers it same as the rest.
    queryset = JobImage.objects.select_related('job', 'job__joborder', 'createdby', 'editedby').order_by('-id')
    serializer_class = JobImageSerializer
    permission_classes = [IsOrderUser]
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ['job']

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)

    def perform_destroy(self, instance):
        if not can_delete_job_subresource(self.request.user, instance.job):
            raise PermissionDenied("Only this job's order creator can delete this row.")
        instance.delete()


class JobItemAttributeViewSet(viewsets.ModelViewSet):
    queryset = JobItemAttribute.objects.select_related('job', 'job__joborder', 'item_attirbuate').order_by('id')
    serializer_class = JobItemAttributeSerializer
    permission_classes = [IsOrderUser]
    filterset_fields = ['job']

    def perform_destroy(self, instance):
        if not can_delete_job_subresource(self.request.user, instance.job):
            raise PermissionDenied("Only this job's order creator can delete this row.")
        instance.delete()


class JobCoaViewSet(viewsets.ModelViewSet):
    queryset = JobCoa.objects.select_related('job', 'job__joborder', 'standard_parameter').order_by('id')
    serializer_class = JobCoaSerializer
    permission_classes = [IsOrderUser]
    filterset_fields = ['job']

    def perform_destroy(self, instance):
        if not can_delete_job_subresource(self.request.user, instance.job):
            raise PermissionDenied("Only this job's order creator can delete this row.")
        instance.delete()


class ProcessReportViewSet(viewsets.ReadOnlyModelViewSet):
    """Mirrors processlist — a cross-job production-floor report (GET
    filters only, no inline editing in the old template either). Kept
    separate from JobProcessViewSet, whose 'job' filter is an exact-match
    used by the job detail page's sub-resource table; JobProcessFilter's
    'job' filter is instead an icontains search on the job's itemname, to
    match the old report's own filter form."""
    queryset = JobProcess.objects.select_related(
        'job', 'job__joborder__customer', 'job__itemmaster', 'process', 'unit',
    ).prefetch_related('jobreport', 'jobreport__unit').order_by('-job__film_size')
    serializer_class = ProcessReportSerializer
    permission_classes = [IsOrderUser]
    filterset_class = JobProcessFilter

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        total_qty = round(queryset.aggregate(Sum('qty'))['qty__sum'] or 0)
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page if page is not None else queryset, many=True)
        response = self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)
        response.data['total_qty'] = total_qty
        return response


class JobMaterialReportViewSet(viewsets.ReadOnlyModelViewSet):
    """Mirrors jobmateriallist — same reasoning as ProcessReportViewSet:
    separate from JobMaterialViewSet's exact-match 'job' filter."""
    queryset = JobMaterial.objects.select_related(
        'job', 'job__joborder__customer', 'materialname', 'item_mat_type', 'item_grade',
    ).order_by('-size')
    serializer_class = JobMaterialReportSerializer
    permission_classes = [IsOrderUser]
    filterset_class = JobMaterialFilter


class JobChangeLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = JobChangeLog.objects.select_related('job', 'changed_by')
    serializer_class = JobChangeLogSerializer
    permission_classes = [IsOrderUser]
    filterset_fields = ['job']


class BulkMaterialRateView(APIView):
    """Mirrors the old `rate` view exactly: given a material/type/grade and
    a rate, backfills every currently-unrated (or effectively zero, <=0.1)
    Stockdetail row matching that combination — a stock-wide catch-up, not
    a single-record edit."""
    permission_classes = [IsOrderUser]

    def post(self, request):
        serializer = BulkMaterialRateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        base = Stockdetail.objects.filter(
            materialname_id=data['materialname'],
            item_mat_type_id=data['item_mat_type'],
            item_grade_id=data['item_grade'],
        )
        updated = base.filter(rate__isnull=True).update(rate=data['rate'])
        updated += base.filter(rate__lte=0.1).update(rate=data['rate'])
        return Response({'updated': updated})


class AssignMarketingPersonView(APIView):
    """Mirrors assign_marketing_person exactly: sets the customer's default
    marketing_person, and backfills it onto every one of that customer's
    jobs (via itemmaster__itemcustomer) that doesn't have one yet."""
    permission_classes = [IsOrderUser]

    def post(self, request):
        serializer = AssignMarketingPersonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = serializer.validated_data['customer']
        marketing_person = serializer.validated_data['marketing_person']

        updated_count = Job.objects.filter(
            itemmaster__itemcustomer=customer, marketing_person__isnull=True,
        ).update(marketing_person=marketing_person)

        customer.marketing_person = marketing_person
        customer.save(update_fields=['marketing_person'])

        return Response({'updated_count': updated_count})


class GetMarketingPersonView(APIView):
    """Mirrors get_marketing_person exactly — given a customer, returns
    their current default marketing_person (used to pre-fill the order/job
    forms client-side)."""
    permission_classes = [IsOrderUser]

    def get(self, request):
        customer_id = request.query_params.get('customer_id')
        data = {'marketing_person_id': None, 'marketing_person_name': None}
        if customer_id:
            customer = Customer.objects.filter(id=customer_id).select_related('marketing_person').first()
            if customer and customer.marketing_person:
                data['marketing_person_id'] = customer.marketing_person.id
                data['marketing_person_name'] = (
                    customer.marketing_person.get_full_name() or customer.marketing_person.username
                )
        return Response(data)


class StockdetailLookupViewSet(viewsets.ReadOnlyModelViewSet):
    """Lets the frontend pick which stock lot to allot against a
    JobMaterial requirement. ?jobmaterial=<id> mirrors
    JobMaterialStatusForm's exact matching logic: same material and mat
    type (NOT grade — the old form never filters on it), qc_status Ok,
    balance>0 (physical stock left) AND available>0 (not already fully
    allotted elsewhere), and either an unsized lot or one at least as
    wide as the requirement minus a 15mm trim tolerance (a roll can be
    slit narrower but never widened). ?include=<stockdetail id> mirrors
    the form's elif self.instance.pk branch: when editing an existing
    allotment, its current lot stays selectable even if it no longer
    passes the filters above (e.g. it's since been fully allotted)."""
    serializer_class = StockdetailLookupSerializer
    permission_classes = [IsOrderUser]
    filterset_fields = ['materialname', 'item_mat_type']

    def get_queryset(self):
        qs = Stockdetail.objects.filter(available__gt=0, balance__gt=0, qc_status='Ok').select_related(
            'materialname', 'item_mat_type', 'item_grade',
        )
        jobmaterial_id = self.request.query_params.get('jobmaterial')
        if jobmaterial_id:
            jm = JobMaterial.objects.filter(id=jobmaterial_id).select_related('materialname', 'item_mat_type').first()
            if not jm:
                return qs.none()
            sizes = (jm.size or 0) - 15
            qs = qs.filter(materialname=jm.materialname, item_mat_type=jm.item_mat_type).filter(
                Q(size__isnull=True) | Q(size__gte=sizes)
            )
        include_id = self.request.query_params.get('include')
        if include_id:
            qs = Stockdetail.objects.filter(id=include_id).select_related(
                'materialname', 'item_mat_type', 'item_grade',
            ) | qs
        return qs.order_by('materialname', 'size', 'micron')


class JobMaterialStatusViewSet(viewsets.ModelViewSet):
    """Mirrors production:jobmaterialstatusedit — allotting a specific
    Stockdetail lot against a JobMaterial's requirement. filterset_fields
    supports both '?jobmaterial=<id>' (one material row's allotments) and
    '?jobmaterial__job=<id>' (a whole job's Material Allotment tab)."""
    queryset = JobMaterialStatus.objects.select_related(
        'jobmaterial', 'jobmaterial__job', 'allote', 'allote__materialname', 'createdby', 'editedby',
    ).order_by('-id')
    serializer_class = JobMaterialStatusSerializer
    permission_classes = [IsOrderUser]
    filterset_fields = ['jobmaterial', 'jobmaterial__job']

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)

    def perform_destroy(self, instance):
        if not can_delete_material_allotment(self.request.user):
            raise PermissionDenied('Only an admin can remove a material allotment.')
        instance.delete()
