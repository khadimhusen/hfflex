from rest_framework import serializers

from itemmaster.models import Machine
from .models import MachineSchedule


class MachineLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Machine
        fields = ['id', 'machinename']


class MachineScheduleSerializer(serializers.ModelSerializer):
    """Scoped to creating/viewing/editing a job's own schedule entries from
    the job detail page -- NOT a stand-in for the planning app's own
    machine-board workflow (start/complete/reorder/downtime/idle slots),
    which stays exactly as it is in the old app.

    status/queue_position/start_time/end_time stay read-only here: a new
    entry always lands as Pending at the next free queue position for its
    machine (mirrors MachineSchedule.clean()'s auto-assignment, which only
    runs via full_clean() -- never invoked by plain ModelSerializer.save())."""
    machine_display = serializers.CharField(source='machine.machinename', read_only=True)
    unit_display = serializers.CharField(source='unit.unit', read_only=True, default=None)
    process_display = serializers.CharField(source='jobprocess.process.process', read_only=True, default=None)
    job_id = serializers.IntegerField(source='jobprocess.job_id', read_only=True)
    createdby_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)

    class Meta:
        model = MachineSchedule
        fields = [
            'id', 'jobprocess', 'process_display', 'job_id', 'machine', 'machine_display',
            'qty', 'unit', 'unit_display', 'persons_assigned', 'remark',
            'status', 'queue_position', 'start_time', 'end_time',
            'created', 'createdby', 'createdby_name', 'edited', 'editedby',
        ]
        read_only_fields = [
            'status', 'queue_position', 'start_time', 'end_time',
            'created', 'createdby', 'edited', 'editedby',
        ]
