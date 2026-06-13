from datetime import timedelta
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from django.http import JsonResponse


def get_planning_role(user):
    if user.is_superuser:
        return 'manager'

    departments = user.department.values_list('department_name', flat=True)

    if 'manager' in departments:
        return 'manager'
    if 'shiftsupervisor' in departments:
        return 'supervisor'
    if 'machine' in departments:
        try:
            if user.machine:
                return 'operator'
        except Exception:
            pass

    return None


def get_operator_machine(user):
    try:
        return user.machine
    except Exception:
        return None


def can_manage_schedule(user):
    return get_planning_role(user) in ('manager', 'supervisor')


def is_operator(user):
    return get_planning_role(user) == 'operator'


def recalculate_timeline(machine):
    from .models import MachineSchedule

    running = (
        MachineSchedule.objects
        .filter(machine=machine, queue_position=0)
        .first()
    )

    pending = list(
        MachineSchedule.objects
        .filter(machine=machine, queue_position__gt=0, status='Pending')
        .order_by('queue_position')
    )

    hold = list(
        MachineSchedule.objects
        .filter(machine=machine, queue_position__gt=0, status='Hold')
        .order_by('queue_position')
    )

    all_active = pending + hold
    offset = 1000

    # Two-step reposition — pending first, hold at bottom
    for i, schedule in enumerate(all_active):
        MachineSchedule.objects.filter(pk=schedule.pk).update(
            queue_position=offset + i + 1
        )
    for i, schedule in enumerate(all_active):
        MachineSchedule.objects.filter(pk=schedule.pk).update(
            queue_position=i + 1
        )

    # Determine chain anchor
    if running:
        if not running.start_time or not running.estimated_duration:
            return
        chain_end = running.end_time if running.end_time else (
                running.start_time + running.estimated_duration
        )
        MachineSchedule.objects.filter(pk=running.pk).update(end_time=chain_end)
    else:
        last_completed = (
            MachineSchedule.objects
            .filter(machine=machine, queue_position=-1)
            .exclude(end_time=None)
            .order_by('-end_time')
            .first()
        )
        if last_completed:
            chain_end = last_completed.end_time
        elif pending and pending[0].start_time:
            chain_end = pending[0].start_time
        else:
            return

    # Chain all active schedules
    for schedule in all_active:
        if not schedule.estimated_duration:
            continue
        start = chain_end
        end = start + schedule.estimated_duration
        MachineSchedule.objects.filter(pk=schedule.pk).update(
            start_time=start,
            end_time=end,
        )
        chain_end = end


def recalculate_timeline(machine):
    from .models import MachineSchedule

    # --- Running job ---
    running = (
        MachineSchedule.objects
        .filter(machine=machine, queue_position=0)
        .first()
    )

    # --- Pending jobs in order (excluding Hold) ---
    pending = list(
        MachineSchedule.objects
        .filter(machine=machine, queue_position__gt=0, status='Pending')
        .order_by('queue_position')
    )

    # --- Hold jobs (always at bottom) ---
    hold = list(
        MachineSchedule.objects
        .filter(machine=machine, queue_position__gt=0, status='Hold')
        .order_by('queue_position')
    )

    # --- Reassign queue positions ---
    # Pending: 1, 2, 3...
    # Hold: after all pending
    offset = 1000
    all_active = pending + hold

    # Step 1 — move all to temp positions to avoid conflicts
    for i, schedule in enumerate(all_active):
        MachineSchedule.objects.filter(pk=schedule.pk).update(
            queue_position=offset + i + 1
        )

    # Step 2 — assign final positions
    for i, schedule in enumerate(all_active):
        MachineSchedule.objects.filter(pk=schedule.pk).update(
            queue_position=i + 1
        )

    # --- Determine chain anchor ---
    if running:
        if not running.start_time or not running.estimated_duration:
            return
        if running.end_time:
            chain_end = running.end_time
        else:
            chain_end = running.start_time + running.estimated_duration
        MachineSchedule.objects.filter(pk=running.pk).update(
            end_time=chain_end
        )
    else:
        last_completed = (
            MachineSchedule.objects
            .filter(machine=machine, queue_position=-1)
            .exclude(end_time=None)
            .order_by('-end_time')
            .first()
        )
        if last_completed:
            chain_end = last_completed.end_time
        elif pending and pending[0].start_time:
            chain_end = pending[0].start_time
        else:
            return

    # --- Chain pending only (hold rows get times but no meaningful start) ---
    for schedule in all_active:
        if not schedule.estimated_duration:
            continue
        start = chain_end
        end = start + schedule.estimated_duration
        MachineSchedule.objects.filter(pk=schedule.pk).update(
            start_time=start,
            end_time=end,
        )
        chain_end = end


def planning_access_required(view_func):

    def wrapper(request, machine_id, *args, **kwargs):
        role = get_planning_role(request.user)
        if role is None:
            return HttpResponseForbidden("You don't have access to planning.")

        if role == 'operator':
            op_machine = get_operator_machine(request.user)
            if not op_machine:
                return HttpResponseForbidden("No machine assigned to your account.")
            if op_machine.id != machine_id:
                # Redirect to their own machine instead of 403
                return redirect('planning:machine_schedule', machine_id=op_machine.id)

        return view_func(request, machine_id, *args, **kwargs)
    return wrapper

def manager_or_supervisor_required(view_func):
    """Block operators from management actions"""

    def wrapper(request, machine_id, *args, **kwargs):
        role = get_planning_role(request.user)
        if role not in ('manager', 'supervisor'):
            return JsonResponse(
                {'status': 'error', 'message': 'Permission denied.'},
                status=403
            )
        return view_func(request, machine_id, *args, **kwargs)
    return wrapper