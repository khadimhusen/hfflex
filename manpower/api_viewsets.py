from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from employee.models import Worker
from itemmaster.models import Problem
from .filters import ShiftFilter, DowntimeFilter
from .models import Machine, Shift, Activity, ShiftPerson, DowntimeReport
from .api_serializers import (
    MachineLookupSerializer, WorkerLookupSerializer, ProblemLookupSerializer,
    ShiftSerializer, ShiftListSerializer, ActivitySerializer, ShiftPersonSerializer, DowntimeReportSerializer,
)
from .permissions import IsManpowerUser
from .querysets import can_approve_shift


class MachineLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Machine.objects.filter(active=True).order_by('machinename')
    serializer_class = MachineLookupSerializer
    permission_classes = [IsManpowerUser]


class WorkerLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Worker.objects.filter(is_active=True).order_by('worker_name')
    serializer_class = WorkerLookupSerializer
    permission_classes = [IsManpowerUser]


class ProblemLookupViewSet(viewsets.ReadOnlyModelViewSet):
    """Downtime reasons -- mirrors DowntimeReportForm's queryset."""
    queryset = Problem.objects.filter(is_active=True).order_by('problem')
    serializer_class = ProblemLookupSerializer
    permission_classes = [IsManpowerUser]


class ShiftViewSet(viewsets.ModelViewSet):
    """Mirrors shiftlist/newshift/shiftdetail. Deletion was never offered
    by the old app (no delete view for a Shift), so it's left off here too."""
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    queryset = Shift.objects.select_related('machine', 'createdby', 'editedby').prefetch_related(
        'activity__jobid', 'activity__downtimes__reason', 'shiftperson__person',
    )
    permission_classes = [IsManpowerUser]
    filterset_class = ShiftFilter

    def get_serializer_class(self):
        if self.action == 'list':
            return ShiftListSerializer
        return ShiftSerializer

    def perform_create(self, serializer):
        # Mirrors newshift()'s get_or_create -- creating a Shift that
        # already exists for this machine/shift/date just returns the
        # existing one instead of erroring, since the old view's own
        # get_or_create had no uniqueness error path either.
        machine = serializer.validated_data['machine']
        shift_val = serializer.validated_data['shift']
        production_date = serializer.validated_data['production_date']
        existing = Shift.objects.filter(
            machine=machine, shift=shift_val, production_date=production_date,
        ).first()
        if existing:
            serializer.instance = existing
            return
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.is_approved:
            raise ValidationError('This shift is already approved and can no longer be edited.')
        serializer.save(editedby=self.request.user)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Mirrors approveshift() -- old view had no permission check at
        all (not even login_required); real check added here."""
        if not can_approve_shift(request.user):
            raise PermissionDenied('Only a director can approve a shift.')
        shift = self.get_object()
        shift.is_approved = True
        shift.save(update_fields=['is_approved'])
        return Response(ShiftSerializer(shift).data)


class ActivityViewSet(viewsets.ModelViewSet):
    queryset = Activity.objects.select_related('shift', 'jobid').prefetch_related('downtimes__reason')
    serializer_class = ActivitySerializer
    permission_classes = [IsManpowerUser]
    filterset_fields = ['shift']

    def _check_not_approved(self, shift):
        if shift.is_approved:
            raise ValidationError('This shift is already approved and can no longer be edited.')

    def perform_create(self, serializer):
        self._check_not_approved(serializer.validated_data['shift'])
        serializer.save()

    def perform_update(self, serializer):
        self._check_not_approved(serializer.instance.shift)
        serializer.save()

    def perform_destroy(self, instance):
        self._check_not_approved(instance.shift)
        instance.delete()


class ShiftPersonViewSet(viewsets.ModelViewSet):
    http_method_names = ['get', 'post', 'delete', 'head', 'options']
    queryset = ShiftPerson.objects.select_related('shift', 'person')
    serializer_class = ShiftPersonSerializer
    permission_classes = [IsManpowerUser]
    filterset_fields = ['shift']

    def perform_create(self, serializer):
        shift = serializer.validated_data['shift']
        if shift.is_approved:
            raise ValidationError('This shift is already approved and can no longer be edited.')
        serializer.save()

    def perform_destroy(self, instance):
        if instance.shift.is_approved:
            raise ValidationError('This shift is already approved and can no longer be edited.')
        instance.delete()


class DowntimeReportViewSet(viewsets.ModelViewSet):
    """Also serves the standalone Downtime List page (?activity__shift__
    machine=&activity__shift__shift=&reason=&date__gt=&date__lt=)."""
    queryset = DowntimeReport.objects.select_related(
        'reason', 'activity__shift__machine', 'activity__jobid',
    ).prefetch_related('activity__shift__shiftperson__person')
    serializer_class = DowntimeReportSerializer
    permission_classes = [IsManpowerUser]
    filterset_class = DowntimeFilter

    def _check_not_approved(self, activity):
        if activity.shift.is_approved:
            raise ValidationError('This shift is already approved and can no longer be edited.')

    def perform_create(self, serializer):
        self._check_not_approved(serializer.validated_data['activity'])
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        self._check_not_approved(serializer.instance.activity)
        serializer.save(editedby=self.request.user)

    def perform_destroy(self, instance):
        self._check_not_approved(instance.activity)
        instance.delete()
