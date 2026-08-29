from datetime import timedelta

from rest_framework import viewsets

from itemmaster.models import Machine
from .models import MachineSchedule
from .api_serializers import MachineLookupSerializer, MachineScheduleSerializer
from .permissions import IsPlanningUser


class MachineLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Machine.objects.filter(active=True).order_by('machinename')
    serializer_class = MachineLookupSerializer
    permission_classes = [IsPlanningUser]
    search_fields = ['machinename']


class MachineScheduleViewSet(viewsets.ModelViewSet):
    """Job-scoped slice of the planning board — filter with
    ?jobprocess__job=<id> to list one job's own schedule entries. Create/
    edit/delete here deliberately never touch start/complete/reorder/
    downtime/idle-slot logic; that remains the dedicated machine-schedule
    board's job (planning/views.py), untouched by this API."""
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    queryset = MachineSchedule.objects.select_related(
        'machine', 'unit', 'jobprocess__job', 'jobprocess__process',
    ).filter(schedule_type='Production')
    serializer_class = MachineScheduleSerializer
    permission_classes = [IsPlanningUser]
    filterset_fields = ['jobprocess', 'jobprocess__job']

    def perform_create(self, serializer):
        machine = serializer.validated_data['machine']
        last = MachineSchedule.objects.for_machine(machine).pending().order_by('-queue_position').first()
        next_position = (last.queue_position + 1) if last else 1
        serializer.save(
            schedule_type='Production',
            queue_position=next_position,
            estimated_duration=timedelta(0),
            createdby=self.request.user,
        )

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)
