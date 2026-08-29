from django.contrib.auth.models import User
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from customer.models import Customer, Address
from material.models import Unit, Material, MatType, Grade
from itemmaster.models import ItemMaster, Process, Color, AttributeMaster, StdParameter, PouchType, LamiRubber
from preorder.models import JobName
from .models import Order, Job, JobMaterial, JobProcess, JobColor, JobImage, JobItemAttribute, JobCoa
from .api_serializers import (
    OrderSerializer, JobSerializer, CustomerLookupSerializer, AddressLookupSerializer,
    MarketingPersonLookupSerializer, UnitLookupSerializer, ItemMasterLookupSerializer, PrejobLookupSerializer,
    MaterialLookupSerializer, MatTypeLookupSerializer, GradeLookupSerializer, ProcessLookupSerializer,
    ColorLookupSerializer, AttributeMasterLookupSerializer, StdParameterLookupSerializer,
    PouchTypeLookupSerializer, LamiRubberLookupSerializer,
    JobMaterialSerializer, JobProcessSerializer, JobColorSerializer, JobImageSerializer,
    JobItemAttributeSerializer, JobCoaSerializer,
)
from .permissions import IsOrderUser
from .querysets import can_edit_order, can_cancel_job, can_delete_job_subresource
from .filters import OrderFilter, JobFilter


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
