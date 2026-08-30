from rest_framework import serializers

from employee.models import Worker
from itemmaster.models import Problem
from .models import Machine, Shift, Activity, ShiftPerson, DowntimeReport


class MachineLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Machine
        fields = ['id', 'machinename']


class WorkerLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Worker
        fields = ['id', 'worker_name']


class ProblemLookupSerializer(serializers.ModelSerializer):
    """Downtime reasons -- mirrors DowntimeReportForm's
    Problem.objects.filter(is_active=True) queryset."""

    class Meta:
        model = Problem
        fields = ['id', 'problem']


class DowntimeReportSerializer(serializers.ModelSerializer):
    reason_display = serializers.CharField(source='reason.problem', read_only=True, default=None)
    shift_display = serializers.CharField(source='activity.shift.__str__', read_only=True)
    job_itemname = serializers.CharField(source='activity.jobid.itemname', read_only=True, default=None)
    persons = serializers.SerializerMethodField()

    class Meta:
        model = DowntimeReport
        fields = [
            'id', 'activity', 'shift_display', 'job_itemname', 'persons', 'reason', 'reason_display', 'downtime',
            'created', 'createdby', 'edited', 'editedby',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']

    def get_persons(self, obj):
        return [sp.person.worker_name for sp in obj.activity.shift.shiftperson.select_related('person').all()]


class ActivitySerializer(serializers.ModelSerializer):
    job_itemname = serializers.CharField(source='jobid.itemname', read_only=True, default=None)
    makereadytime = serializers.ReadOnlyField()
    totaltime = serializers.ReadOnlyField()
    runningtime = serializers.ReadOnlyField()
    totaldowntime = serializers.ReadOnlyField()
    downtimes = DowntimeReportSerializer(many=True, read_only=True)

    class Meta:
        model = Activity
        fields = [
            'id', 'shift', 'jobid', 'job_itemname', 'qty', 'speed', 'makeready', 'makereadytime',
            'rolls', 'tag', 'lot', 'totaltime', 'runningtime', 'totaldowntime', 'downtimes',
        ]


class ShiftPersonSerializer(serializers.ModelSerializer):
    person_name = serializers.CharField(source='person.worker_name', read_only=True)

    class Meta:
        model = ShiftPerson
        fields = ['id', 'shift', 'person', 'person_name']


class ShiftListSerializer(serializers.ModelSerializer):
    """Lightweight row for shiftlist.html's table."""
    machine_display = serializers.CharField(source='machine.machinename', read_only=True)
    actualtime = serializers.ReadOnlyField()
    efficiency = serializers.ReadOnlyField()

    class Meta:
        model = Shift
        fields = [
            'id', 'shift', 'machine', 'machine_display', 'production_date',
            'actualtime', 'efficiency', 'is_approved',
        ]


class ShiftSerializer(serializers.ModelSerializer):
    """Full shift detail -- mirrors shiftdetail.html's activity/person
    tables plus the shift-level totals shown in its header/footer."""
    machine_display = serializers.CharField(source='machine.machinename', read_only=True)
    createdby_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)
    actualtime = serializers.ReadOnlyField()
    totalroll = serializers.ReadOnlyField()
    totaltag = serializers.ReadOnlyField()
    totallot = serializers.ReadOnlyField()
    totaldowntime = serializers.ReadOnlyField()
    totalqty = serializers.ReadOnlyField()
    totalmakereadytime = serializers.ReadOnlyField()
    totalrunningtime = serializers.ReadOnlyField()
    wastetime = serializers.ReadOnlyField()
    efficiency = serializers.ReadOnlyField()
    activity = ActivitySerializer(many=True, read_only=True)
    shiftperson = ShiftPersonSerializer(many=True, read_only=True)

    class Meta:
        model = Shift
        fields = [
            'id', 'shift', 'machine', 'machine_display', 'production_date', 'is_approved',
            'actualtime', 'totalroll', 'totaltag', 'totallot', 'totaldowntime', 'totalqty',
            'totalmakereadytime', 'totalrunningtime', 'wastetime', 'efficiency',
            'activity', 'shiftperson',
            'created', 'createdby', 'createdby_name', 'edited', 'editedby',
        ]
        read_only_fields = ['created', 'createdby', 'edited', 'editedby']
