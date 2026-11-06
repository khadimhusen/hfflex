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


def can_edit_completed(user, machine=None):
    """Django staff users (is_staff) may correct a COMPLETED schedule row, on
    top of having some planning role. A staff operator only on their own
    machine. Everyone else sees completed rows read-only."""
    if not (user.is_authenticated and user.is_staff):
        return False
    role = get_planning_role(user)
    if role is None:
        return False
    if role == 'operator' and machine is not None:
        op_machine = get_operator_machine(user)
        return bool(op_machine and op_machine.id == machine.id)
    return True


class CompletedEditError(ValueError):
    """A completed-row edit the user must fix; the message is shown to them."""


def set_completed_variance(schedule_pk):
    """A completed row's variance is its actual duration minus its estimate,
    exactly as complete_schedule() sets it. Call again whenever the actual
    times or anything feeding the estimate (tasks, downtime, speed...) change."""
    from .models import MachineSchedule
    row = MachineSchedule.objects.get(pk=schedule_pk)
    variance = None
    if row.start_time and row.end_time:
        variance = (row.end_time - row.start_time) - (row.estimated_duration or timedelta(0))
    MachineSchedule.objects.filter(pk=row.pk).update(time_variance=variance)


def edit_completed_schedule(schedule, user, *, start_time=None, end_time=None, speed=None,
                            persons_assigned=None, remark=None, raw_material_status=None):
    """Staff correction of a completed row (shared by the API and the old
    Django view). None means "leave as is". An Idle row only takes times.

    Speed and persons follow the same maths as a normal 'basic' edit (running
    duration = qty / speed; makeready re-derived from the tasks for the new
    persons), then the variance is recomputed, and the machine's timeline is
    refreshed -- when nothing is running, the newest completed end time is
    where the queued jobs' planned times start."""
    from django.db import IntegrityError, transaction
    from django.utils import timezone
    from .choices import MATERIAL_STATUS
    from .models import MachineSchedule
    from .signals import task_duration_mins

    if schedule.queue_position != -1:
        raise CompletedEditError('Only completed jobs can be edited here.')

    new_start = start_time or schedule.start_time
    new_end = end_time or schedule.end_time
    if new_start and new_end and new_end < new_start:
        raise CompletedEditError('End time cannot be earlier than start time.')

    changes = {}
    if start_time:
        changes['start_time'] = start_time
    if end_time:
        changes['end_time'] = end_time

    if schedule.schedule_type == 'Production':
        makeready = schedule.makeready_duration or timedelta(0)
        running = schedule.running_duration or timedelta(0)

        if persons_assigned is not None:
            if persons_assigned < 1:
                raise CompletedEditError('Persons assigned must be at least 1.')
            if persons_assigned != schedule.persons_assigned:
                tasks = schedule.productiontasks.select_related('task')
                makeready = timedelta(minutes=sum(
                    task_duration_mins(pt.task, pt.qty, persons_assigned)
                    for pt in tasks if pt.task.category == 'Makeready'
                ))
                changes['persons_assigned'] = persons_assigned
                changes['makeready_duration'] = makeready

        if speed is not None:
            if speed < 1:
                raise CompletedEditError('Speed must be at least 1.')
            qty = float(schedule.qty or 0)
            running = timedelta(minutes=round(qty / speed) if qty else 0)
            changes['speed'] = speed
            changes['running_duration'] = running

        if 'makeready_duration' in changes or 'running_duration' in changes:
            changes['estimated_duration'] = makeready + running + (schedule.downtime_duration or timedelta(0))

        if remark is not None:
            changes['remark'] = remark
        if raw_material_status is not None:
            if raw_material_status not in dict(MATERIAL_STATUS):
                raise CompletedEditError('Unknown raw material status.')
            changes['raw_material_status'] = raw_material_status

    changes['editedby'] = user
    changes['edited'] = timezone.now()
    try:
        with transaction.atomic():
            MachineSchedule.objects.filter(pk=schedule.pk).update(**changes)
            set_completed_variance(schedule.pk)
    except IntegrityError as exc:
        raise CompletedEditError('End time cannot be earlier than start time.') from exc
    recalculate_timeline(schedule.machine)


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