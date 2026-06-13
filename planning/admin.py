from django.contrib import admin, messages
from django.db import transaction
from django.db.models import F
from .models import MachineSchedule, ProductionTask, IdleTime
from .utils import recalculate_timeline



class ProductionTaskInline(admin.TabularInline):
    model = ProductionTask
    extra = 0
    fields = ['task', 'qty', 'time_per_task', 'total_time']  # category removed
    readonly_fields = ['total_time']


@admin.register(IdleTime)
class IdleTimeAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['name']



@admin.register(ProductionTask)
class ProductionTaskAdmin(admin.ModelAdmin):
    list_display = [
        'machine_schedule', 'task', 'get_category',
        'qty', 'time_per_task', 'total_time'
    ]
    list_filter = ['task__category', 'machine_schedule__machine']
    search_fields = ['task__task']
    readonly_fields = ['total_time']

    @admin.display(description='Category')
    def get_category(self, obj):
        return obj.task.category



@admin.action(description='Reopen selected schedules — set to Pending (move to end of queue)')
def set_to_pending(modeladmin, request, queryset):
    # Filter to only Completed schedules
    schedules = queryset.filter(status='Completed', queue_position=-1)

    if not schedules.exists():
        modeladmin.message_user(
            request,
            'No Completed schedules found in selection. Only Completed schedules can be reopened.',
            messages.WARNING
        )
        return

    machines = set()

    with transaction.atomic():
        for schedule in schedules.select_related('machine'):
            machine = schedule.machine

            # Find end of queue for this machine
            last = (
                MachineSchedule.objects
                .filter(machine=machine, queue_position__gt=0)
                .order_by('-queue_position')
                .first()
            )
            new_pos = (last.queue_position + 1) if last else 1

            # Reopen — move to end of queue as Pending
            MachineSchedule.objects.filter(pk=schedule.pk).update(
                status='Pending',
                queue_position=new_pos,
                start_time=None,
                end_time=None,
            )

            machines.add(machine)

    for machine in machines:
        recalculate_timeline(machine)

    count = schedules.count()
    modeladmin.message_user(
        request,
        f'{count} schedule(s) reopened and moved to end of queue.',
        messages.SUCCESS
    )


@admin.register(MachineSchedule)
class MachineScheduleAdmin(admin.ModelAdmin):
    actions = [set_to_pending]
    list_display = [
        'machine', 'schedule_type', 'jobprocess',
        'queue_position', 'status',
        'makeready_duration', 'running_duration',
        'downtime_duration', 'estimated_duration',
    ]
    list_filter = ['machine', 'schedule_type', 'status']
    search_fields = ['jobprocess__job__id', 'machine__machinename']
    readonly_fields = [
        'makeready_duration', 'running_duration',
        'downtime_duration', 'estimated_duration',
        'created', 'edited',
    ]
