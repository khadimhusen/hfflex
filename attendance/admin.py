from django.contrib import admin

from .models import AttendanceDay, PunchLog, ShiftAssignment


@admin.register(ShiftAssignment)
class ShiftAssignmentAdmin(admin.ModelAdmin):
    """View only: shifts are given on the Shift Roster page, which keeps a worker's entries from
    overlapping and works the days out again."""
    list_display = ('worker', 'from_date', 'to_date', 'shift')
    list_filter = ('shift',)
    search_fields = ('worker__worker_name', 'worker__emp_code')
    date_hierarchy = 'from_date'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PunchLog)
class PunchLogAdmin(admin.ModelAdmin):
    list_display = ('emp_code', 'worker', 'punched_at', 'source', 'device')
    list_filter = ('source',)
    search_fields = ('emp_code', 'worker__worker_name')
    raw_id_fields = ('worker',)
    date_hierarchy = 'punched_at'


@admin.register(AttendanceDay)
class AttendanceDayAdmin(admin.ModelAdmin):
    list_display = ('worker', 'date', 'status', 'shift', 'in_time', 'out_time', 'worked_minutes', 'is_manual')
    list_filter = ('status', 'shift', 'is_manual')
    search_fields = ('worker__worker_name', 'worker__emp_code')
    raw_id_fields = ('worker',)
    date_hierarchy = 'date'
