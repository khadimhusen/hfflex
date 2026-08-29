from rest_framework import serializers

from itemmaster.models import Machine
from .models import MachineSchedule, IdleTime, ProductionTask, MachineDowntime


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


# ---- Full machine-schedule-board API (mirrors planning/views.py) ------

class IdleTimeSerializer(serializers.ModelSerializer):
    class Meta:
        model = IdleTime
        fields = ['id', 'name', 'category', 'is_active']


class ProductionTaskSerializer(serializers.ModelSerializer):
    task_name = serializers.CharField(source='task.task', read_only=True)
    category = serializers.CharField(source='task.category', read_only=True)
    effective_duration = serializers.ReadOnlyField()

    class Meta:
        model = ProductionTask
        fields = ['id', 'task', 'task_name', 'category', 'qty', 'time_per_task', 'effective_duration']
        read_only_fields = ['task']


class MachineDowntimeSerializer(serializers.ModelSerializer):
    reason_name = serializers.CharField(source='reason.name', read_only=True)
    recorded_by_name = serializers.CharField(source='recorded_by.get_full_name', read_only=True, default=None)
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = MachineDowntime
        fields = [
            'id', 'reason', 'reason_name', 'duration_seconds', 'notes',
            'created', 'recorded_by', 'recorded_by_name',
        ]

    def get_duration_seconds(self, obj):
        return int(obj.duration.total_seconds()) if obj.duration else 0


class MachineScheduleBoardSerializer(serializers.ModelSerializer):
    """Read-mostly view of one schedule row for the machine board -- every
    field a schedule row needs to display. Mutations go through the
    dedicated action endpoints (start/complete/edit-schedule/etc.), which
    replicate the old view functions' exact queue-position/timeline math,
    not a generic PATCH."""
    machine_display = serializers.CharField(source='machine.machinename', read_only=True)
    unit_display = serializers.CharField(source='unit.unit', read_only=True, default=None)
    job_id = serializers.IntegerField(source='jobprocess.job_id', read_only=True)
    job_itemname = serializers.CharField(source='jobprocess.job.itemname', read_only=True, default=None)
    process_display = serializers.CharField(source='jobprocess.process.process', read_only=True, default=None)
    no_of_ply = serializers.CharField(source='jobprocess.no_of_ply', read_only=True, default=None)
    idle_reason_name = serializers.CharField(source='idle_reason.name', read_only=True, default=None)
    createdby_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)
    editedby_name = serializers.CharField(source='editedby.get_full_name', read_only=True, default=None)

    estimated_seconds = serializers.SerializerMethodField()
    makeready_seconds = serializers.SerializerMethodField()
    running_seconds = serializers.SerializerMethodField()
    downtime_seconds = serializers.SerializerMethodField()
    time_variance_seconds = serializers.ReadOnlyField()

    class Meta:
        model = MachineSchedule
        fields = [
            'id', 'schedule_type', 'jobprocess', 'job_id', 'job_itemname', 'process_display', 'no_of_ply',
            'idle_reason', 'idle_reason_name', 'idle_notes', 'raw_material_status',
            'machine', 'machine_display', 'qty', 'unit', 'unit_display', 'speed',
            'status', 'persons_assigned', 'queue_position', 'start_time', 'end_time',
            'makeready_seconds', 'running_seconds', 'downtime_seconds', 'estimated_seconds',
            'time_variance_seconds', 'remark',
            'created', 'createdby', 'createdby_name', 'edited', 'editedby', 'editedby_name',
        ]

    def get_estimated_seconds(self, obj):
        return int(obj.estimated_duration.total_seconds()) if obj.estimated_duration else 0

    def get_makeready_seconds(self, obj):
        return int(obj.makeready_duration.total_seconds()) if obj.makeready_duration else 0

    def get_running_seconds(self, obj):
        return int(obj.running_duration.total_seconds()) if obj.running_duration else 0

    def get_downtime_seconds(self, obj):
        return int(obj.downtime_duration.total_seconds()) if obj.downtime_duration else 0
