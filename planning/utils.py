from datetime import timedelta
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.db.models import F


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
    if 'viewplanning' in departments:
        return 'viewer'

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

    # Safety check — if nothing to reposition, skip entirely
    if not all_active:
        if running:
            if running.start_time and running.estimated_duration:
                chain_end = running.start_time + running.estimated_duration
                MachineSchedule.objects.filter(pk=running.pk).update(end_time=chain_end)
        return



    # Step 1 — move all to temp positions (preserves relative order)
    MachineSchedule.objects.filter(
        machine=machine,
        queue_position__gt=0,
        status__in=['Pending', 'Hold']
    ).update(queue_position=F('queue_position') + 50000)

    # Re-fetch after shift so any rows inserted between the initial fetch and
    # Step 1 are included; ordering by shifted value preserves the original order.
    all_active = list(
        MachineSchedule.objects
        .filter(machine=machine, queue_position__gt=50000, status__in=['Pending', 'Hold'])
        .order_by('queue_position')
    )

    # Step 2 — assign final positions (1, 2, 3, ...)
    for i, schedule in enumerate(all_active):
        MachineSchedule.objects.filter(pk=schedule.pk).update(
            queue_position=i + 1
        )


    # Determine chain anchor
    if running:
        if not running.start_time or not running.estimated_duration:
            return
        chain_end = running.start_time + running.estimated_duration
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
                return redirect('planning:machine_schedule', machine_id=op_machine.id)

        return view_func(request, machine_id, *args, **kwargs)
    return wrapper


def manager_or_supervisor_required(view_func):
    def wrapper(request, machine_id, *args, **kwargs):
        role = get_planning_role(request.user)
        if role not in ('manager', 'supervisor'):
            return JsonResponse(
                {'status': 'error', 'message': 'Permission denied.'},
                status=403
            )
        return view_func(request, machine_id, *args, **kwargs)
    return wrapper