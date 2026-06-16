from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.views.decorators.http import require_POST
from django.db import transaction
from .utils import recalculate_timeline, planning_access_required
import json
from datetime import timedelta
from itemmaster.models import Machine, ItemProcess
from .models import MachineSchedule, IdleTime, ProductionTask, MachineDowntime
from datetime import datetime
from django.utils.dateparse import parse_datetime
from django.db.models import Sum

from .utils import get_planning_role, manager_or_supervisor_required
from django.db.models import F


@login_required(login_url='/login/')
@planning_access_required
def machine_schedule(request, machine_id):
    machine = get_object_or_404(Machine, pk=machine_id)
    role = get_planning_role(request.user)

    # Managers and supervisors see all active machines
    # Operators see only their machine
    if role in ('manager', 'supervisor'):
        machines = Machine.objects.filter(active=True)
    else:
        machines = Machine.objects.filter(pk=machine_id)

    completed_qs = (
        MachineSchedule.objects
        .filter(machine=machine, queue_position=-1)
        .select_related('jobprocess__job', 'idle_reason')
        .order_by('-end_time')[:5]
    )
    completed = sorted(completed_qs, key=lambda x: x.end_time or x.created)

    completed_count = MachineSchedule.objects.filter(
        machine=machine, queue_position=-1
    ).count()

    running = (
        MachineSchedule.objects
        .filter(machine=machine, queue_position=0)
        .select_related('jobprocess__job', 'idle_reason')
        .first()
    )
    queue = (
        MachineSchedule.objects
        .filter(machine=machine, queue_position__gt=0)
        .select_related('jobprocess__job', 'idle_reason')
        .order_by('queue_position')
    )

    for s in queue:
        s.estimated_seconds = int(
            s.estimated_duration.total_seconds()
        ) if s.estimated_duration else 0

    idle_reasons = IdleTime.objects.filter(is_active=True)
    downtime_reasons = IdleTime.objects.filter(category='Unplanned', is_active=True)

    context = {
        'machine': machine,
        'machines': machines,
        'running': running,
        'queue': queue,
        'idle_reasons': idle_reasons,
        'downtime_reasons': downtime_reasons,
        'pending_count': queue.filter(schedule_type='Production', status='Pending').count(),
        'idle_count': queue.filter(schedule_type='Idle').count(),
        'completed': completed,
        'completed_count': completed_count,
        'role': role,
        'is_manager': role == 'manager',
        'is_supervisor': role == 'supervisor',
        'is_operator': role == 'operator',
    }
    return render(request, 'planning/machine_schedule.html', context)


# ------------------------------------------------------------------ #
# Edit MachineSchedule                                                 #
# ------------------------------------------------------------------ #


@login_required(login_url='/login/')
@require_POST
def edit_schedule(request, machine_id, schedule_id):
    machine = get_object_or_404(Machine, pk=machine_id)
    schedule = get_object_or_404(
        MachineSchedule, pk=schedule_id, machine=machine,
        queue_position__gte=0
    )
    role = get_planning_role(request.user)
    if role is None:
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)

    try:
        data = json.loads(request.body)
        action = data.get('action', 'basic')

        # Operators can only do basic — and only speed field
        if role == 'operator':
            if action != 'basic':
                return JsonResponse(
                    {'status': 'error', 'message': 'Permission denied.'},
                    status=403
                )
            # Only update speed
            new_speed = int(data.get('speed') or schedule.speed or 60)
            qty = float(schedule.qty or 0)
            running_mins = round(qty / new_speed) if new_speed and qty else 0
            running_dur = timedelta(minutes=running_mins)
            new_estimated = (
                    (schedule.makeready_duration or timedelta(0)) +
                    running_dur +
                    (schedule.downtime_duration or timedelta(0))
            )
            raw_material_status = data.get('material_status', schedule.raw_material_status)
            MachineSchedule.objects.filter(pk=schedule.pk).update(
                speed=new_speed,
                running_duration=running_dur,
                estimated_duration=new_estimated,
                editedby=request.user,
                raw_material_status=raw_material_status
            )
            recalculate_timeline(machine)
            return JsonResponse({'status': 'ok'})

        if action == 'basic':
            new_speed = int(data.get('speed') or schedule.speed or 60)
            new_persons = int(data.get('persons_assigned') or schedule.persons_assigned or 1)

            # Store old persons for comparison
            old_persons = schedule.persons_assigned

            qty = float(schedule.qty or 0)
            running_mins = round(qty / new_speed) if new_speed and qty else 0
            running_dur = timedelta(minutes=running_mins)

            new_estimated = (
                    (schedule.makeready_duration or timedelta(0)) +
                    running_dur +
                    (schedule.downtime_duration or timedelta(0))
            )

            schedule.speed = new_speed
            schedule.persons_assigned = new_persons
            schedule.running_duration = running_dur
            schedule.estimated_duration = new_estimated
            schedule.remark = data.get('remark', '')
            schedule.editedby = request.user
            schedule.raw_material_status = data.get('material_status', schedule.raw_material_status)
            print('material status', schedule.raw_material_status)
            schedule.save(update_fields=[
                'speed', 'persons_assigned', 'running_duration',
                'estimated_duration', 'remark', 'raw_material_status',
                'editedby', 'edited'
            ])

            # Recalculate makeready if persons changed
            if new_persons != old_persons:
                tasks = schedule.productiontasks.select_related('task').all()
                makeready_mins = sum(
                    pt.effective_duration for pt in tasks
                    if pt.task.category == 'Makeready'
                )
                new_makeready = timedelta(minutes=makeready_mins)
                new_estimated = (
                        new_makeready +
                        running_dur +
                        (schedule.downtime_duration or timedelta(0))
                )
                MachineSchedule.objects.filter(pk=schedule.pk).update(
                    makeready_duration=new_makeready,
                    estimated_duration=new_estimated,
                )

            recalculate_timeline(machine)
            return JsonResponse({'status': 'ok'})


        elif action == 'split':
            split_qty = float(data.get('split_qty') or 0)
            if not split_qty or split_qty <= 0:
                return JsonResponse({'status': 'error', 'message': 'Split qty must be greater than 0.'}, status=400)
            if split_qty >= float(schedule.qty or 0):
                return JsonResponse({'status': 'error', 'message': 'Split qty must be less than current qty.'},
                                    status=400)

            remainder_qty = float(schedule.qty) - split_qty
            speed = schedule.speed or 60

            with transaction.atomic():
                new_running_mins = round(split_qty / speed)
                new_running_dur = timedelta(minutes=new_running_mins)
                new_estimated_dur = (
                        (schedule.makeready_duration or timedelta(0)) +
                        new_running_dur +
                        (schedule.downtime_duration or timedelta(0))
                )
                schedule.qty = split_qty
                schedule.running_duration = new_running_dur
                schedule.estimated_duration = new_estimated_dur
                schedule.editedby = request.user
                schedule.save(update_fields=[
                    'qty', 'running_duration', 'estimated_duration', 'editedby', 'edited'
                ])

                last = (
                    MachineSchedule.objects
                    .filter(machine=machine, queue_position__gt=0)
                    .order_by('-queue_position')
                    .first()
                )
                next_position = (last.queue_position + 1) if last else 1

                rem_running_mins = round(remainder_qty / speed)
                rem_running_dur = timedelta(minutes=rem_running_mins)
                rem_estimated = (
                        (schedule.makeready_duration or timedelta(0)) +
                        rem_running_dur +
                        (schedule.downtime_duration or timedelta(0))
                )

                new_schedule = MachineSchedule.objects.create(
                    schedule_type=schedule.schedule_type,
                    jobprocess=schedule.jobprocess,
                    machine=machine,
                    qty=remainder_qty,
                    unit=schedule.unit,
                    speed=schedule.speed,
                    persons_assigned=schedule.persons_assigned,
                    status='Pending',
                    makeready_duration=schedule.makeready_duration,
                    running_duration=rem_running_dur,
                    downtime_duration=schedule.downtime_duration,
                    estimated_duration=rem_estimated,
                    queue_position=next_position,
                    createdby=request.user,
                )

                old_tasks = schedule.productiontasks.select_related('task').all()
                ProductionTask.objects.bulk_create([
                    ProductionTask(
                        machine_schedule=new_schedule,
                        task=t.task,
                        qty=t.qty,
                        time_per_task=t.time_per_task,
                    )
                    for t in old_tasks
                ])

            recalculate_timeline(machine)
            return JsonResponse({'status': 'ok', 'new_schedule_id': new_schedule.id})



        elif action == 'change_machine':

            if schedule.queue_position == 0:
                return JsonResponse(

                    {'status': 'error', 'message': 'Cannot change machine of a running schedule.'},

                    status=400

                )

            new_machine_id = data.get('new_machine_id')

            if not new_machine_id:
                return JsonResponse({'status': 'error', 'message': 'No machine selected.'}, status=400)

            new_machine = get_object_or_404(Machine, pk=new_machine_id)

            if new_machine == machine:
                return JsonResponse({'status': 'error', 'message': 'Same machine selected.'}, status=400)

            with transaction.atomic():

                try:

                    item_process = ItemProcess.objects.get(

                        itemmaster=schedule.jobprocess.job.itemmaster,

                        process=schedule.jobprocess.process,

                        process_count=schedule.jobprocess.process_count,

                        machine=new_machine,

                    )

                    new_speed = item_process.speed or new_machine.mode_speed or 60

                except ItemProcess.DoesNotExist:

                    new_speed = new_machine.mode_speed or 60

                new_tasks = new_machine.tasks.all()

                qty = float(schedule.qty or 0)

                running_mins = round(qty / new_speed) if new_speed and qty else 30

                running_dur = timedelta(minutes=running_mins)

                color_count = schedule.jobprocess.job.itemmaster.itemcolors.count() or 1

                makeready_mins = sum(

                    t.duration * t.persons_required * (color_count if t.qty_from_colors else 1)

                    for t in new_tasks if t.category == 'Makeready'

                )

                downtime_mins = sum(

                    t.duration * t.persons_required * (color_count if t.qty_from_colors else 1)

                    for t in new_tasks if t.category == 'Breakdown'

                )

                makeready_dur = timedelta(minutes=makeready_mins)

                downtime_dur = timedelta(minutes=downtime_mins)

                estimated_dur = makeready_dur + running_dur + downtime_dur

                old_position = schedule.queue_position

                offset = 1000

                # Step 1 — move this schedule to safe temp position on old machine

                MachineSchedule.objects.filter(pk=schedule.pk).update(

                    queue_position=offset + 500

                )

                # Step 2 — close gap on old machine

                MachineSchedule.objects.filter(

                    machine=machine,

                    queue_position__gt=old_position,

                    queue_position__lt=offset

                ).update(queue_position=F('queue_position') + offset)

                MachineSchedule.objects.filter(

                    machine=machine,

                    queue_position__gt=offset,

                    queue_position__lt=offset + 500

                ).update(queue_position=F('queue_position') - offset - 1)

                # Step 3 — find end of new machine queue

                last = (

                    MachineSchedule.objects

                    .filter(machine=new_machine, queue_position__gt=0)

                    .order_by('-queue_position')

                    .first()

                )

                next_position = (last.queue_position + 1) if last else 1

                # Step 4 — delete old ProductionTasks

                MachineSchedule.objects.get(pk=schedule.pk).productiontasks.all().delete()

                # Step 5 — update schedule to new machine at final position

                MachineSchedule.objects.filter(pk=schedule.pk).update(

                    machine=new_machine,

                    speed=new_speed,

                    running_duration=running_dur,

                    makeready_duration=makeready_dur,

                    downtime_duration=downtime_dur,

                    estimated_duration=estimated_dur,

                    queue_position=next_position,

                    editedby=request.user,

                )

                # Step 6 — create new ProductionTasks from new machine templates

                schedule.refresh_from_db()

                ProductionTask.objects.bulk_create([

                    ProductionTask(

                        machine_schedule=schedule,

                        task=t,

                        time_per_task=t.duration,

                        qty=color_count if t.qty_from_colors else 1,

                    )

                    for t in new_tasks

                ])

            recalculate_timeline(machine)

            recalculate_timeline(new_machine)

            return JsonResponse({'status': 'ok'})


        else:
            return JsonResponse({'status': 'error', 'message': 'Unknown action.'}, status=400)

    except Exception as e:
        print(f"edit_schedule error: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required(login_url='/login/')
@require_POST
def start_schedule(request, machine_id, schedule_id):
    machine = get_object_or_404(Machine, pk=machine_id)
    schedule = get_object_or_404(
        MachineSchedule, pk=schedule_id, machine=machine,
        queue_position__gt=0
    )
    try:
        if schedule.queue_position != 1:
            return JsonResponse(
                {'status': 'error',
                 'message': 'Only the first job in queue can be started.'},
                status=400
            )

        data = json.loads(request.body)
        actual_start = data.get('start_time')

        if actual_start:
            if len(actual_start) == 16:
                actual_start = actual_start + ':00'
            actual_start = parse_datetime(actual_start)
            if not actual_start:
                return JsonResponse(
                    {'status': 'error', 'message': 'Invalid start time format.'},
                    status=400
                )
        else:
            actual_start = datetime.now()

        # Calculate variance
        expected_start = schedule.start_time
        variance = (actual_start - expected_start) if expected_start else None

        with transaction.atomic():
            # Complete current running job if any
            MachineSchedule.objects.filter(
                machine=machine, queue_position=0
            ).update(
                queue_position=-1,
                status='Completed',
                end_time=datetime.now(),
            )

            # Start this job
            MachineSchedule.objects.filter(pk=schedule.pk).update(
                queue_position=0,
                status='Running',
                start_time=actual_start,
                time_variance=variance,
            )

            # Shift remaining pending down by 1
            MachineSchedule.objects.filter(
                machine=machine, queue_position__gt=1
            ).update(queue_position=F('queue_position') + 1000)

            MachineSchedule.objects.filter(
                machine=machine, queue_position__gt=1000
            ).update(queue_position=F('queue_position') - 1001)

        recalculate_timeline(machine)
        return JsonResponse({'status': 'ok'})

    except Exception as e:
        print(f"start_schedule error: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required(login_url='/login/')
@require_POST
def complete_schedule(request, machine_id, schedule_id):
    machine = get_object_or_404(Machine, pk=machine_id)
    schedule = get_object_or_404(
        MachineSchedule, pk=schedule_id, machine=machine,
        queue_position=0
    )
    try:
        data = json.loads(request.body)
        actual_end = data.get('end_time')

        if actual_end:
            if len(actual_end) == 16:
                actual_end = actual_end + ':00'
            actual_end = parse_datetime(actual_end)
            if not actual_end:
                return JsonResponse(
                    {'status': 'error', 'message': 'Invalid end time format.'},
                    status=400
                )
        else:
            actual_end = datetime.now()

        # Calculate variance
        expected_end = (
            schedule.start_time + schedule.estimated_duration
            if schedule.start_time and schedule.estimated_duration
            else None
        )
        # variance = actual_duration - estimated_duration
        # estimated already includes downtime so variance is pure unexplained delay
        actual_duration = actual_end - schedule.start_time if schedule.start_time else None
        variance = (actual_duration - schedule.estimated_duration) if actual_duration else None

        with transaction.atomic():
            MachineSchedule.objects.filter(pk=schedule.pk).update(
                queue_position=-1,
                status='Completed',
                end_time=actual_end,
                time_variance=variance,
            )

        recalculate_timeline(machine)
        return JsonResponse({'status': 'ok'})

    except Exception as e:
        print(f"complete_schedule error: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required(login_url='/login/')
@manager_or_supervisor_required
@require_POST
def reorder_queue(request, machine_id):
    machine = get_object_or_404(Machine, pk=machine_id)
    try:
        data = json.loads(request.body)
        with transaction.atomic():
            # Step 1 — shift to large temporary positions to avoid conflicts
            # e.g. 1,2,3 become 1001,1002,1003
            offset = 2000
            for item in data:
                MachineSchedule.objects.filter(
                    pk=item['id'],
                    machine=machine,
                    queue_position__gt=0
                ).update(queue_position=item['queue_position'] + offset)

            # Step 2 — set final positions
            for item in data:
                MachineSchedule.objects.filter(
                    pk=item['id'],
                    machine=machine,
                ).update(queue_position=item['queue_position'])

        recalculate_timeline(machine)

        return JsonResponse({'status': 'ok'})
    except Exception as e:
        print(f"reorder_queue error: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required(login_url='/login/')
@manager_or_supervisor_required
@require_POST
def add_idle_slot(request, machine_id):
    machine = get_object_or_404(Machine, pk=machine_id)
    try:
        data = json.loads(request.body)
        idle_reason = get_object_or_404(IdleTime, pk=data['idle_reason_id'])
        hours = int(data.get('hours', 0))
        mins = int(data.get('mins', 0))
        insert_after = int(data.get('insert_after', -1))
        notes = data.get('notes', '')

        from datetime import timedelta
        duration = timedelta(hours=hours, minutes=mins)

        with transaction.atomic():
            if insert_after >= 0:
                new_position = insert_after + 1
                offset = 1000

                # Step 1 — move affected rows to safe temporary positions
                MachineSchedule.objects.filter(
                    machine=machine,
                    queue_position__gt=insert_after
                ).update(queue_position=F('queue_position') + offset)

                # Step 2 — move them to final positions (shifted up by 1)
                MachineSchedule.objects.filter(
                    machine=machine,
                    queue_position__gt=offset
                ).update(queue_position=F('queue_position') - offset + 1)

                # Step 3 — now create the idle slot at the gap
                schedule = MachineSchedule.objects.create(
                    machine=machine,
                    schedule_type='Idle',
                    idle_reason=idle_reason,
                    idle_notes=notes,
                    estimated_duration=duration,
                    queue_position=new_position,
                    status='Pending',
                    createdby=request.user,
                )


            else:
                # Add at end
                last = (
                    MachineSchedule.objects
                    .filter(machine=machine, queue_position__gt=0)
                    .order_by('-queue_position')
                    .first()
                )
                new_position = (last.queue_position + 1) if last else 1

                schedule = MachineSchedule.objects.create(
                    machine=machine,
                    schedule_type='Idle',
                    idle_reason=idle_reason,
                    idle_notes=notes,
                    estimated_duration=duration,
                    queue_position=new_position,
                    status='Pending',
                    createdby=request.user,
                )
        recalculate_timeline(machine)

        return JsonResponse({
            'status': 'ok',
            'id': schedule.id,
            'queue_position': schedule.queue_position,
        })

    except Exception as e:
        print(f"add_idle_slot error: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required(login_url='/login/')
@manager_or_supervisor_required
@require_POST
def edit_idle_slot(request, machine_id, schedule_id):
    machine = get_object_or_404(Machine, pk=machine_id)
    schedule = get_object_or_404(
        MachineSchedule,
        pk=schedule_id,
        machine_id=machine_id,
        schedule_type='Idle'
    )
    try:
        data = json.loads(request.body)
        idle_reason = get_object_or_404(IdleTime, pk=data['idle_reason_id'])
        hours = int(data.get('hours', 0))
        mins = int(data.get('mins', 0))
        from datetime import timedelta
        schedule.idle_reason = idle_reason
        schedule.idle_notes = data.get('notes', '')
        schedule.estimated_duration = timedelta(hours=hours, minutes=mins)
        schedule.editedby = request.user
        schedule.save(update_fields=[
            'idle_reason', 'idle_notes', 'estimated_duration', 'editedby', 'edited'
        ])
        recalculate_timeline(machine)
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required(login_url='/login/')
@manager_or_supervisor_required
@require_POST
def delete_idle_slot(request, machine_id, schedule_id):
    machine = get_object_or_404(Machine, pk=machine_id)  # ← machine defined here
    schedule = get_object_or_404(
        MachineSchedule,
        pk=schedule_id,
        machine=machine,
        schedule_type='Idle',
        queue_position__gt=0
    )
    try:
        with transaction.atomic():
            pos = schedule.queue_position
            schedule.delete()
            offset = 1000

            # Step 1 — shift to temporary positions
            MachineSchedule.objects.filter(
                machine=machine,
                queue_position__gt=pos
            ).update(queue_position=F('queue_position') + offset)

            # Step 2 — shift back down by offset+1 to close the gap
            MachineSchedule.objects.filter(
                machine=machine,
                queue_position__gt=offset
            ).update(queue_position=F('queue_position') - offset - 1)

        return JsonResponse({'status': 'ok'})
    except Exception as e:
        print(f"delete_idle_slot error: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required(login_url='/login/')
@manager_or_supervisor_required
def schedule_tasks(request, machine_id, schedule_id):
    machine = get_object_or_404(Machine, pk=machine_id)
    schedule = get_object_or_404(
        MachineSchedule, pk=schedule_id, machine=machine,
        queue_position__gte=0
    )

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            tasks = data.get('tasks', [])
            for t in tasks:
                task = get_object_or_404(
                    ProductionTask, pk=t['id'], machine_schedule=schedule
                )
                task.qty = t['qty']
                task.time_per_task = t['time_per_task']
                task.save()  # triggers post_save signal → recalculates durations
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            print(f"schedule_tasks POST error: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

    # GET — return tasks as JSON for modal
    try:
        tasks = schedule.productiontasks.select_related('task').all()
        data = [
            {
                'id': t.id,
                'task': t.task.task,
                'category': t.task.category,
                'qty': t.qty,
                'time_per_task': t.time_per_task,
                'total_time': t.effective_duration,
            }
            for t in tasks
        ]
        return JsonResponse({'status': 'ok', 'tasks': data})
    except Exception as e:
        print(f"schedule_tasks GET error: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required(login_url='/login/')
def add_downtime(request, machine_id, schedule_id):
    machine = get_object_or_404(Machine, pk=machine_id)
    schedule = get_object_or_404(
        MachineSchedule, pk=schedule_id,
        machine=machine,
        queue_position=0,
        schedule_type='Production'
    )

    if request.method == 'GET':
        # Return existing downtimes
        downtimes = schedule.downtimes.select_related('reason').all()
        data = [
            {
                'id': d.id,
                'reason_id': d.reason.id,
                'reason': d.reason.name,
                'hours': int(d.duration.total_seconds()) // 3600,
                'mins': (int(d.duration.total_seconds()) % 3600) // 60,
                'notes': d.notes or '',
                'created': d.created.strftime('%d/%m %H:%M'),
            }
            for d in downtimes
        ]
        return JsonResponse({'status': 'ok', 'downtimes': data})

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action', 'add')

            if action == 'add':
                reason = get_object_or_404(
                    IdleTime, pk=data['reason_id'], category='Unplanned'
                )
                hours = int(data.get('hours', 0))
                mins = int(data.get('mins', 0))
                if not hours and not mins:
                    return JsonResponse(
                        {'status': 'error', 'message': 'Duration required.'},
                        status=400
                    )
                MachineDowntime.objects.create(
                    machine_schedule=schedule,
                    reason=reason,
                    duration=timedelta(hours=hours, minutes=mins),
                    notes=data.get('notes', ''),
                    recorded_by=request.user,
                )

            elif action == 'edit':
                downtime = get_object_or_404(
                    MachineDowntime, pk=data['downtime_id'],
                    machine_schedule=schedule
                )
                hours = int(data.get('hours', 0))
                mins = int(data.get('mins', 0))
                if not hours and not mins:
                    return JsonResponse(
                        {'status': 'error', 'message': 'Duration required.'},
                        status=400
                    )
                downtime.reason = get_object_or_404(
                    IdleTime, pk=data['reason_id'], category='Unplanned'
                )
                downtime.duration = timedelta(hours=hours, minutes=mins)
                downtime.notes = data.get('notes', '')
                downtime.save(update_fields=['reason', 'duration', 'notes'])

            elif action == 'delete':
                downtime = get_object_or_404(
                    MachineDowntime, pk=data['downtime_id'],
                    machine_schedule=schedule
                )
                downtime.delete()

            # Recalculate downtime_duration + estimated_duration
            total_downtime = (
                    MachineDowntime.objects
                    .filter(machine_schedule=schedule)
                    .aggregate(total=Sum('duration'))['total']
                    or timedelta(0)
            )
            new_estimated = (
                    (schedule.makeready_duration or timedelta(0)) +
                    (schedule.running_duration or timedelta(0)) +
                    total_downtime
            )
            MachineSchedule.objects.filter(pk=schedule.pk).update(
                downtime_duration=total_downtime,
                estimated_duration=new_estimated,
            )
            recalculate_timeline(machine)
            return JsonResponse({'status': 'ok'})

        except Exception as e:
            print(f"add_downtime error: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


from .pdfs import generate_schedule_pdf

@login_required(login_url='/login/')
def schedule_pdf(request):
    role = get_planning_role(request.user)
    if role not in ('manager', 'supervisor'):
        return HttpResponseForbidden("Permission denied.")

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="machine_schedule_'
        f'{datetime.now().strftime("%Y%m%d_%H%M")}.pdf"'
    )
    generate_schedule_pdf(response)
    return response