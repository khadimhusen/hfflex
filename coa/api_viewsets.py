from datetime import datetime

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from production.models import DispatchRegister
from .models import Coa, TestParameter
from .api_serializers import CoaSerializer, TestParameterSerializer, DispatchRegisterLookupSerializer
from .permissions import IsCoaUser, CanApproveCoa, IsStaffForReopen


class DispatchRegisterLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DispatchRegister.objects.select_related('customer').order_by('-dispatchdate')
    serializer_class = DispatchRegisterLookupSerializer
    permission_classes = [IsCoaUser]


class CoaViewSet(viewsets.ModelViewSet):
    queryset = Coa.objects.select_related(
        'jobname', 'delivery_challan', 'delivery_challan__customer', 'createdby', 'approvedby', 'editedby',
    ).order_by('-year', '-serial')
    serializer_class = CoaSerializer
    permission_classes = [IsCoaUser]
    filterset_fields = ['jobname']

    def perform_create(self, serializer):
        # jobname is read-only on the serializer (set once, here) --
        # mirrors add_coa() taking the job from the URL, never from the
        # submitted form body.
        job_id = self.request.data.get('jobname')
        if not job_id:
            raise ValidationError({'jobname': 'This field is required.'})
        serializer.save(createdby=self.request.user, jobname_id=job_id)

    def perform_update(self, serializer):
        # Mirrors coa_edit()'s hard block -- CoaSerializer already makes
        # the non-admin fields read-only once approved, but an approved
        # COA should reject an edit attempt outright rather than silently
        # drop the blocked fields, matching the old view's explicit error.
        instance = serializer.instance
        if instance.is_approved:
            admin_fields = {'work_order', 'delivery_challan', 'invoice_no', 'qty'}
            if set(self.request.data.keys()) - admin_fields:
                raise PermissionDenied(f'COA {instance.coa_number} is already approved and cannot be edited.')
        serializer.save(editedby=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[CanApproveCoa])
    def approve(self, request, pk=None):
        coa = self.get_object()
        coa.approvedby = request.user
        coa.approve_date = datetime.now()
        coa.save()
        return Response(self.get_serializer(coa).data)

    @action(detail=True, methods=['post'], permission_classes=[IsStaffForReopen])
    def reopen(self, request, pk=None):
        coa = self.get_object()
        coa.approvedby = None
        coa.approve_date = None
        coa.save(update_fields=['approvedby', 'approve_date'])
        return Response(self.get_serializer(coa).data)


class TestParameterViewSet(viewsets.ModelViewSet):
    queryset = TestParameter.objects.select_related('coa', 'standard_parameter').order_by('id')
    serializer_class = TestParameterSerializer
    permission_classes = [IsCoaUser]
    filterset_fields = ['coa']

    def perform_destroy(self, instance):
        # Create/update are blocked in TestParameterSerializer.validate(),
        # but destroy() never runs the serializer -- same hard block needs
        # repeating here.
        if instance.coa.is_approved:
            raise PermissionDenied(f'COA {instance.coa.coa_number} is already approved and cannot be edited.')
        instance.delete()
