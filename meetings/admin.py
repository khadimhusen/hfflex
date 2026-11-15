from django.contrib import admin

from .models import ActionItem, Meeting, MeetingAttendee


class AttendeeInline(admin.TabularInline):
    model = MeetingAttendee
    extra = 0


class ActionItemInline(admin.TabularInline):
    model = ActionItem
    extra = 0
    raw_id_fields = ('task',)


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = ('number', 'title', 'meeting_type', 'meeting_date', 'status', 'created_by')
    list_filter = ('status', 'meeting_type')
    search_fields = ('number', 'title', 'minutes')
    readonly_fields = ('number',)
    inlines = [AttendeeInline, ActionItemInline]
