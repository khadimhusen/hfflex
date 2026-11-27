from rest_framework import serializers

from employee.models import Worker

from .models import AttendanceDay, PunchLog


def hours_text(minutes):
    return f'{minutes // 60}:{minutes % 60:02d}' if minutes else ''


class PunchLogSerializer(serializers.ModelSerializer):
    worker_name = serializers.CharField(source='worker.worker_name', read_only=True, default=None)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PunchLog
        fields = ['id', 'worker', 'worker_name', 'emp_code', 'punched_at', 'source', 'source_display', 'device',
                  'note', 'created', 'created_by_name']
        read_only_fields = fields

    def get_created_by_name(self, obj):
        user = obj.created_by
        return (user.get_full_name().strip() or user.username) if user else ''


class PunchCreateSerializer(serializers.Serializer):
    """A punch typed in by hand (a worker who forgot to punch, a broken reader)."""
    worker = serializers.PrimaryKeyRelatedField(queryset=Worker.objects.all())
    punched_at = serializers.DateTimeField()
    note = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')


class AttendanceDaySerializer(serializers.ModelSerializer):
    worker_name = serializers.CharField(source='worker.worker_name', read_only=True)
    emp_code = serializers.CharField(source='worker.emp_code', read_only=True, default='')
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    worked_text = serializers.SerializerMethodField()
    overtime_text = serializers.SerializerMethodField()
    break_text = serializers.SerializerMethodField()
    edited_by_name = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceDay
        fields = ['id', 'worker', 'worker_name', 'emp_code', 'date', 'status', 'status_display', 'shift', 'in_time',
                  'out_time', 'worked_minutes', 'worked_text', 'overtime_minutes', 'overtime_text',
                  'break_start', 'break_end', 'break_minutes', 'break_text', 'remarks',
                  'is_manual', 'edited', 'edited_by_name']
        read_only_fields = fields

    def get_worked_text(self, obj):
        return hours_text(obj.worked_minutes)

    def get_overtime_text(self, obj):
        return hours_text(obj.overtime_minutes)

    def get_break_text(self, obj):
        return hours_text(obj.break_minutes)

    def get_edited_by_name(self, obj):
        user = obj.edited_by
        return (user.get_full_name().strip() or user.username) if user else ''


class DayWriteSerializer(serializers.Serializer):
    """A person's decision for a worker's day."""
    worker = serializers.PrimaryKeyRelatedField(queryset=Worker.objects.all())
    date = serializers.DateField()
    status = serializers.ChoiceField(choices=AttendanceDay.STATUSES)
    in_time = serializers.DateTimeField(required=False, allow_null=True, default=None)
    out_time = serializers.DateTimeField(required=False, allow_null=True, default=None)
    shift = serializers.ChoiceField(choices=AttendanceDay.SHIFTS, required=False, allow_blank=True, default='')
    remarks = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
