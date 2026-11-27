from django.contrib import admin

from .models import AttendanceDay, PunchLog


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
