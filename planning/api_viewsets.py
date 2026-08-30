import json
from datetime import datetime, timedelta

from django.db import transaction, IntegrityError
from django.db.models import F, Sum
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from itemmaster.models import Machine, ItemProcess
from .models import MachineSchedule, IdleTime, ProductionTask, MachineDowntime
from .api_serializers import (
    MachineLookupSerializer, MachineScheduleSerializer, MachineScheduleBoardSerializer,
    IdleTimeSerializer, ProductionTaskSerializer, MachineDowntimeSerializer,
)
from .permissions import IsPlanningUser
from .utils import (
    get_planning_role, get_operator_machine, can_manage_schedule,
    recalculate_timeline,
)


def task_duration_mins(task, qty, persons_assigned):
    """Verbatim port of planning/views.py's task_duration_mins."""
    if task.persons_required == 0:
        return task.duration * qty
    return round((task.duration * task.persons_required * qty) / persons_assigned)


def require_not_viewer(user):
    role = get_planning_role(user)
    if role is None or role == 'viewer':
        raise PermissionDenied('Permission denied.')
    return role


def require_manager_or_supervisor(user):
    if not can_manage_schedule(user):
        raise PermissionDenied('Only a manager or supervisor can do this.')


def parse_client_datetime(value):
    """Mirrors the old views' 'YYYY-MM-DDTHH:mm' -> add ':00' -> parse_datetime
    handling for start_time/end_time coming from a <input type=datetime-local>."""
    if not value:
        return None
    if len(value) == 16:
        value = value + ':00'
    parsed = parse_datetime(value)
    if not parsed:
        raise ValidationError('Invalid datetime format.')
    return parsed


class MachineLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Machine.objects.filter(active=True).order_by('machinename')
    serializer_class = MachineLookupSerializer
    permission_classes = [IsPlanningUser]
    search_fields = ['machinename']


class IdleTimeLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = IdleTime.objects.filter(is_active=True)
    serializer_class = IdleTimeSerializer
    permission_classes = [IsPlanningUser]


class MachineScheduleViewSet(viewsets.ModelViewSet):
    """Job-scoped CRUD (create/list/update from the job detail page) plus
    every machine-board action from planning/views.py, ported as closely
    to the original as possible: same queue-position offset tricks, same
    role rules, same transaction boundaries. recalculate_timeline() is
    reused directly from planning/utils.py, not reimplemented.

    Deletion is restricted to idle slots only (mirrors delete_idle_slot --
    the old app never exposed a way to delete a production schedule row)."""
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    queryset = MachineSchedule.objects.select_related(
        'machine', 'unit', 'jobprocess__job', 'jobprocess__process', 'idle_reason', 'createdby', 'editedby',
    )
    permission_classes = [IsPlanningUser]
    filterset_fields = ['jobprocess', 'jobprocess__job', 'machine']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return MachineScheduleSerializer
        return MachineScheduleBoardSerializer

    def perform_create(self, serializer):
        machine = serializer.validated_data['machine']
        last = MachineSchedule.objects.for_machine(machine).pending().order_by('-queue_position').first()
        next_position = (last.queue_position + 1) if last else 1
        serializer.save(
            schedule_type='Production',
            queue_position=next_position,
            estimated_duration=timedelta(0),
            createdby=self.request.user,
        )

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)

    def perform_destroy(self, instance):
        if instance.schedule_type != 'Idle' or instance.queue_position <= 0:
            raise ValidationError('Only pending idle slots can be deleted.')
        require_manager_or_supervisor(self.request.user)
        machine = instance.machine
        with transaction.atomic():
            pos = instance.queue_position
            instance.delete()
            offset = 50000
            MachineSchedule.objects.filter(machine=machine, queue_position__gt=pos).update(
                queue_position=F('queue_position') + offset,
            )
            MachineSchedule.objects.filter(machine=machine, queue_position__gt=offset).update(
                queue_position=F('queue_position') - offset - 1,
            )
        recalculate_timeline(machine)

    # ---- start / complete -------------------------------------------------

    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Mirrors start_schedule(): only the front of the queue can start;
        completes whatever was running first, in the same transaction."""
        schedule = get_object_or_404(MachineSchedule, pk=pk, queue_position__gt=0)
        machine = schedule.machine
        require_not_viewer(request.user)

        if schedule.queue_position != 1:
            raise ValidationError('Only the first job in queue can be started.')

        actual_start = parse_client_datetime(request.data.get('start_time')) or datetime.now()

        current_running = MachineSchedule.objects.filter(machine=machine, queue_position=0).first()
        if current_running and current_running.start_time and actual_start < current_running.start_time:
            raise ValidationError(
                'Start time cannot be earlier than the current running job\'s start time '
                f'({current_running.start_time.strftime("%d/%m/%Y %H:%M")}).'
            )

        expected_start = schedule.start_time
        variance = (actual_start - expected_start) if expected_start else None

        try:
            with transaction.atomic():
                if current_running:
                    prev_expected_end = (
                        current_running.start_time + current_running.estimated_duration
                        if current_running.start_time and current_running.estimated_duration else None
                    )
                    prev_variance = (actual_start - prev_expected_end) if prev_expected_end else None
                    MachineSchedule.objects.filter(pk=current_running.pk).update(
                        queue_position=-1, status='Completed', end_time=actual_start, time_variance=prev_variance,
                    )

                MachineSchedule.objects.filter(pk=schedule.pk).update(
                    queue_position=0, status='Running', start_time=actual_start, time_variance=variance,
                )

                MachineSchedule.objects.filter(machine=machine, queue_position__gt=1).update(
                    queue_position=F('queue_position') + 50000,
                )
                MachineSchedule.objects.filter(machine=machine, queue_position__gt=50000).update(
                    queue_position=F('queue_position') - 50001,
                )
        except IntegrityError as e:
            if 'end_time_gte_start_time' in str(e):
                raise ValidationError(
                    'Start time is earlier than the current running job\'s start time.'
                )
            raise ValidationError(str(e))

        recalculate_timeline(machine)
        schedule.refresh_from_db()
        return Response(MachineScheduleBoardSerializer(schedule).data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mirrors complete_schedule()."""
        schedule = get_object_or_404(MachineSchedule, pk=pk, queue_position=0)
        machine = schedule.machine
        require_not_viewer(request.user)

        actual_end = parse_client_datetime(request.data.get('end_time')) or datetime.now()
        actual_duration = actual_end - schedule.start_time if schedule.start_time else None
        variance = (actual_duration - schedule.estimated_duration) if actual_duration else None

        with transaction.atomic():
            MachineSchedule.objects.filter(pk=schedule.pk).update(
                queue_position=-1, status='Completed', end_time=actual_end, time_variance=variance,
            )

        recalculate_timeline(machine)
        schedule.refresh_from_db()
        return Response(MachineScheduleBoardSerializer(schedule).data)

    # ---- edit (basic / split / change_machine) -----------------------------

    @action(detail=True, methods=['post'], url_path='edit-schedule')
    def edit_schedule(self, request, pk=None):
        """Mirrors edit_schedule(): 'basic' (speed/persons/remark/material
        status -- operators may only touch speed on their own machine's
        running/queued row), 'split' (break a queued row into two), and
        'change_machine' (move a queued row to a different machine,
        recomputing its tasks/timings from that machine's own setup)."""
        schedule = get_object_or_404(MachineSchedule, pk=pk, queue_position__gte=0)
        machine = schedule.machine
        role = get_planning_role(request.user)
        if role is None or role == 'viewer':
            raise PermissionDenied('Permission denied.')

        action_name = request.data.get('action', 'basic')

        if role == 'operator':
            if action_name != 'basic':
                raise PermissionDenied('Permission denied.')
            new_speed = int(request.data.get('speed') or schedule.speed or 60)
            qty = float(schedule.qty or 0)
            running_mins = round(qty / new_speed) if new_speed and qty else 0
            running_dur = timedelta(minutes=running_mins)
            new_estimated = (
                (schedule.makeready_duration or timedelta(0)) + running_dur +
                (schedule.downtime_duration or timedelta(0))
            )
            MachineSchedule.objects.filter(pk=schedule.pk).update(
                speed=new_speed, running_duration=running_dur, estimated_duration=new_estimated,
                editedby=request.user,
                raw_material_status=request.data.get('material_status', schedule.raw_material_status),
            )
            recalculate_timeline(machine)
            schedule.refresh_from_db()
            return Response(MachineScheduleBoardSerializer(schedule).data)

        if action_name == 'basic':
            new_speed = int(request.data.get('speed') or schedule.speed or 60)
            new_persons = int(request.data.get('persons_assigned') or schedule.persons_assigned or 1)
            old_persons = schedule.persons_assigned

            qty = float(schedule.qty or 0)
            running_mins = round(qty / new_speed) if new_speed and qty else 0
            running_dur = timedelta(minutes=running_mins)
            new_estimated = (
                (schedule.makeready_duration or timedelta(0)) + running_dur +
                (schedule.downtime_duration or timedelta(0))
            )

            schedule.speed = new_speed
            schedule.persons_assigned = new_persons
            schedule.running_duration = running_dur
            schedule.estimated_duration = new_estimated
            schedule.remark = request.data.get('remark', schedule.remark)
            schedule.editedby = request.user
            schedule.raw_material_status = request.data.get('material_status', schedule.raw_material_status)
            schedule.save(update_fields=[
                'speed', 'persons_assigned', 'running_duration', 'estimated_duration',
                'remark', 'raw_material_status', 'editedby', 'edited',
            ])

            if new_persons != old_persons:
                prod_tasks = schedule.productiontasks.select_related('task').all()
                makeready_mins = sum(
                    task_duration_mins(pt.task, pt.qty, new_persons)
                    for pt in prod_tasks if pt.task.category == 'Makeready'
                )
                new_makeready = timedelta(minutes=makeready_mins)
                new_estimated = new_makeready + running_dur + (schedule.downtime_duration or timedelta(0))
                MachineSchedule.objects.filter(pk=schedule.pk).update(
                    makeready_duration=new_makeready, estimated_duration=new_estimated,
                )

            recalculate_timeline(machine)
            schedule.refresh_from_db()
            return Response(MachineScheduleBoardSerializer(schedule).data)

        elif action_name == 'split':
            split_qty = float(request.data.get('split_qty') or 0)
            if not split_qty or split_qty <= 0:
                raise ValidationError('Split qty must be greater than 0.')
            if split_qty >= float(schedule.qty or 0):
                raise ValidationError('Split qty must be less than current qty.')

            remainder_qty = float(schedule.qty) - split_qty
            speed = schedule.speed or 60

            with transaction.atomic():
                new_running_mins = round(split_qty / speed)
                new_running_dur = timedelta(minutes=new_running_mins)
                new_estimated_dur = (
                    (schedule.makeready_duration or timedelta(0)) + new_running_dur +
                    (schedule.downtime_duration or timedelta(0))
                )
                schedule.qty = split_qty
                schedule.running_duration = new_running_dur
                schedule.estimated_duration = new_estimated_dur
                schedule.editedby = request.user
                schedule.save(update_fields=['qty', 'running_duration', 'estimated_duration', 'editedby', 'edited'])

                last = MachineSchedule.objects.filter(
                    machine=machine, queue_position__gt=0,
                ).order_by('-queue_position').first()
                next_position = (last.queue_position + 1) if last else 1

                rem_running_mins = round(remainder_qty / speed)
                rem_running_dur = timedelta(minutes=rem_running_mins)
                rem_estimated = (
                    (schedule.makeready_duration or timedelta(0)) + rem_running_dur +
                    (schedule.downtime_duration or timedelta(0))
                )

                new_schedule = MachineSchedule.objects.create(
                    schedule_type=schedule.schedule_type, jobprocess=schedule.jobprocess, machine=machine,
                    qty=remainder_qty, unit=schedule.unit, speed=schedule.speed,
                    persons_assigned=schedule.persons_assigned, status='Pending',
                    makeready_duration=schedule.makeready_duration, running_duration=rem_running_dur,
                    downtime_duration=schedule.downtime_duration, estimated_duration=rem_estimated,
                    queue_position=next_position, createdby=request.user,
                )

                old_tasks = schedule.productiontasks.select_related('task').all()
                ProductionTask.objects.bulk_create([
                    ProductionTask(machine_schedule=new_schedule, task=t.task, qty=t.qty, time_per_task=t.time_per_task)
                    for t in old_tasks
                ])

            recalculate_timeline(machine)
            return Response({'status': 'ok', 'new_schedule_id': new_schedule.id})

        elif action_name == 'change_machine':
            if schedule.queue_position == 0:
                raise ValidationError('Cannot change machine of a running schedule.')

            new_machine_id = request.data.get('new_machine_id')
            if not new_machine_id:
                raise ValidationError('No machine selected.')
            new_machine = get_object_or_404(Machine, pk=new_machine_id)
            if new_machine == machine:
                raise ValidationError('Same machine selected.')

            with transaction.atomic():
                try:
                    item_process = ItemProcess.objects.get(
                        itemmaster=schedule.jobprocess.job.itemmaster, process=schedule.jobprocess.process,
                        process_count=schedule.jobprocess.process_count, machine=new_machine,
                    )
                    new_speed = item_process.speed or new_machine.mode_speed or 60
                except ItemProcess.DoesNotExist:
                    new_speed = new_machine.mode_speed or 60

                new_tasks = new_machine.tasks.all()
                qty = float(schedule.qty or 0)
                running_mins = round(qty / new_speed) if new_speed and qty else 30
                running_dur = timedelta(minutes=running_mins)
                color_count = schedule.jobprocess.job.itemmaster.itemcolors.count() or 1
                persons_assigned = new_machine.default_persons or 2

                makeready_mins = sum(
                    task_duration_mins(t, color_count if t.default_qty is None else t.default_qty, persons_assigned)
                    for t in new_tasks if t.category == 'Makeready'
                )
                downtime_mins = sum(
                    task_duration_mins(t, color_count if t.default_qty is None else t.default_qty, persons_assigned)
                    for t in new_tasks if t.category == 'Breakdown'
                )
                makeready_dur = timedelta(minutes=makeready_mins)
                downtime_dur = timedelta(minutes=downtime_mins)
                estimated_dur = makeready_dur + running_dur + downtime_dur

                old_position = schedule.queue_position
                offset = 50000
                MachineSchedule.objects.filter(pk=schedule.pk).update(queue_position=99999)
                MachineSchedule.objects.filter(
                    machine=machine, queue_position__gt=old_position, queue_position__lt=99999,
                ).update(queue_position=F('queue_position') + offset)
                MachineSchedule.objects.filter(
                    machine=machine, queue_position__gt=offset, queue_position__lt=99999,
                ).update(queue_position=F('queue_position') - offset - 1)

                last = MachineSchedule.objects.filter(
                    machine=new_machine, queue_position__gt=0,
                ).order_by('-queue_position').first()
                next_position = (last.queue_position + 1) if last else 1

                MachineSchedule.objects.get(pk=schedule.pk).productiontasks.all().delete()

                MachineSchedule.objects.filter(pk=schedule.pk).update(
                    machine=new_machine, speed=new_speed, persons_assigned=persons_assigned,
                    running_duration=running_dur, makeready_duration=makeready_dur,
                    downtime_duration=downtime_dur, estimated_duration=estimated_dur,
                    queue_position=next_position, editedby=request.user,
                )

                schedule.refresh_from_db()
                ProductionTask.objects.bulk_create([
                    ProductionTask(
                        machine_schedule=schedule, task=t, time_per_task=t.duration,
                        qty=color_count if t.default_qty is None else t.default_qty,
                    )
                    for t in new_tasks
                ])

            recalculate_timeline(machine)
            recalculate_timeline(new_machine)
            schedule.refresh_from_db()
            return Response(MachineScheduleBoardSerializer(schedule).data)

        raise ValidationError('Unknown action.')

    # ---- idle slot edit (add/delete are machine-scoped, see below) --------

    @action(detail=True, methods=['post'], url_path='edit-idle')
    def edit_idle(self, request, pk=None):
        """Mirrors edit_idle_slot()."""
        schedule = get_object_or_404(MachineSchedule, pk=pk, schedule_type='Idle')
        require_manager_or_supervisor(request.user)
        idle_reason = get_object_or_404(IdleTime, pk=request.data.get('idle_reason_id'))
        hours = int(request.data.get('hours', 0))
        mins = int(request.data.get('mins', 0))
        schedule.idle_reason = idle_reason
        schedule.idle_notes = request.data.get('notes', '')
        schedule.estimated_duration = timedelta(hours=hours, minutes=mins)
        schedule.editedby = request.user
        schedule.save(update_fields=['idle_reason', 'idle_notes', 'estimated_duration', 'editedby', 'edited'])
        recalculate_timeline(schedule.machine)
        return Response(MachineScheduleBoardSerializer(schedule).data)

    # ---- production tasks --------------------------------------------------

    @action(detail=True, methods=['get', 'post'])
    def tasks(self, request, pk=None):
        """Mirrors schedule_tasks(), plus a fix the old app was missing:
        editing a task's qty/time (which changes makeready/downtime
        duration) now recalculates the schedule's estimated duration and
        reflows the machine's timeline, same as changing persons_assigned
        already does in edit_schedule()."""
        schedule = get_object_or_404(MachineSchedule, pk=pk, queue_position__gte=0)

        if request.method == 'POST':
            require_manager_or_supervisor(request.user)
            for t in request.data.get('tasks', []):
                task = get_object_or_404(ProductionTask, pk=t['id'], machine_schedule=schedule)
                task.qty = t['qty']
                task.time_per_task = t['time_per_task']
                task.save()

            prod_tasks = schedule.productiontasks.select_related('task').all()
            makeready_mins = sum(
                pt.effective_duration for pt in prod_tasks if pt.task.category == 'Makeready'
            )
            downtime_mins = sum(
                pt.effective_duration for pt in prod_tasks if pt.task.category != 'Makeready'
            )
            new_makeready = timedelta(minutes=makeready_mins)
            new_downtime = timedelta(minutes=downtime_mins)
            new_estimated = new_makeready + (schedule.running_duration or timedelta(0)) + new_downtime
            MachineSchedule.objects.filter(pk=schedule.pk).update(
                makeready_duration=new_makeready,
                downtime_duration=new_downtime,
                estimated_duration=new_estimated,
                editedby=request.user,
            )
            recalculate_timeline(schedule.machine)
            return Response({'status': 'ok'})

        prod_tasks = schedule.productiontasks.select_related('task').all()
        return Response(ProductionTaskSerializer(prod_tasks, many=True).data)

    # ---- downtime -----------------------------------------------------------

    @action(detail=True, methods=['get', 'post'])
    def downtime(self, request, pk=None):
        """Mirrors add_downtime() (GET lists, POST add/edit/delete via
        action field) -- restricted to the currently-running row, same as
        the old view."""
        schedule = get_object_or_404(
            MachineSchedule, pk=pk, queue_position=0, schedule_type='Production',
        )
        require_not_viewer(request.user)

        if request.method == 'GET':
            downtimes = schedule.downtimes.select_related('reason').all()
            return Response(MachineDowntimeSerializer(downtimes, many=True).data)

        action_name = request.data.get('action', 'add')
        if action_name == 'add':
            reason = get_object_or_404(IdleTime, pk=request.data.get('reason_id'), category='Unplanned')
            hours = int(request.data.get('hours', 0))
            mins = int(request.data.get('mins', 0))
            if not hours and not mins:
                raise ValidationError('Duration required.')
            MachineDowntime.objects.create(
                machine_schedule=schedule, reason=reason, duration=timedelta(hours=hours, minutes=mins),
                notes=request.data.get('notes', ''), recorded_by=request.user,
            )
        elif action_name == 'edit':
            downtime = get_object_or_404(MachineDowntime, pk=request.data.get('downtime_id'), machine_schedule=schedule)
            hours = int(request.data.get('hours', 0))
            mins = int(request.data.get('mins', 0))
            if not hours and not mins:
                raise ValidationError('Duration required.')
            downtime.reason = get_object_or_404(IdleTime, pk=request.data.get('reason_id'), category='Unplanned')
            downtime.duration = timedelta(hours=hours, minutes=mins)
            downtime.notes = request.data.get('notes', '')
            downtime.save(update_fields=['reason', 'duration', 'notes'])
        elif action_name == 'delete':
            downtime = get_object_or_404(MachineDowntime, pk=request.data.get('downtime_id'), machine_schedule=schedule)
            downtime.delete()
        else:
            raise ValidationError('Unknown action.')

        total_downtime = (
            MachineDowntime.objects.filter(machine_schedule=schedule).aggregate(total=Sum('duration'))['total']
            or timedelta(0)
        )
        new_estimated = (
            (schedule.makeready_duration or timedelta(0)) + (schedule.running_duration or timedelta(0)) +
            total_downtime
        )
        MachineSchedule.objects.filter(pk=schedule.pk).update(
            downtime_duration=total_downtime, estimated_duration=new_estimated,
        )
        recalculate_timeline(schedule.machine)
        downtimes = schedule.downtimes.select_related('reason').all()
        return Response(MachineDowntimeSerializer(downtimes, many=True).data)

    # ---- detail (completed only) -------------------------------------------

    @action(detail=True, methods=['get'], url_path='detail-info')
    def detail_info(self, request, pk=None):
        """Mirrors schedule_detail()."""
        schedule = get_object_or_404(MachineSchedule, pk=pk, queue_position=-1)
        tasks = schedule.productiontasks.select_related('task').all()
        downtimes = schedule.downtimes.select_related('reason').all()
        return Response({
            'schedule': MachineScheduleBoardSerializer(schedule).data,
            'tasks': ProductionTaskSerializer(tasks, many=True).data,
            'downtimes': MachineDowntimeSerializer(downtimes, many=True).data,
        })


# ---- machine-scoped endpoints (not tied to one schedule row) -------------

class MachineBoardView(APIView):
    """Mirrors machine_schedule(): the full board payload for one machine."""
    permission_classes = [IsPlanningUser]

    def get(self, request, machine_id):
        machine = get_object_or_404(Machine, pk=machine_id)
        role = get_planning_role(request.user)
        if role is None:
            raise PermissionDenied("You don't have access to planning.")

        if role == 'operator':
            op_machine = get_operator_machine(request.user)
            if not op_machine:
                raise PermissionDenied('No machine assigned to your account.')
            if op_machine.id != int(machine_id):
                return Response({'redirect_machine_id': op_machine.id}, status=409)
            machines = Machine.objects.filter(pk=machine_id)
        elif role in ('manager', 'supervisor', 'viewer'):
            machines = Machine.objects.filter(active=True)
        else:
            machines = Machine.objects.filter(pk=machine_id)

        completed_qs = (
            MachineSchedule.objects.filter(machine=machine, queue_position=-1)
            .select_related('jobprocess__job', 'jobprocess__process', 'idle_reason')
            .order_by('-end_time')[:5]
        )
        completed = sorted(completed_qs, key=lambda x: x.end_time or x.created)
        completed_count = MachineSchedule.objects.filter(machine=machine, queue_position=-1).count()

        running = (
            MachineSchedule.objects.filter(machine=machine, queue_position=0)
            .select_related('jobprocess__job', 'jobprocess__process', 'idle_reason')
            .first()
        )

        queue = (
            MachineSchedule.objects.filter(machine=machine, queue_position__gt=0)
            .select_related('jobprocess__job', 'jobprocess__process', 'idle_reason')
            .order_by('queue_position')
        )

        idle_reasons = IdleTime.objects.filter(is_active=True)
        downtime_reasons = IdleTime.objects.filter(category='Unplanned', is_active=True)

        last_completed = (
            MachineSchedule.objects.filter(machine=machine, queue_position=-1)
            .exclude(end_time=None).order_by('-end_time').first()
        )
        if running and running.end_time:
            last_end_time = running.end_time
        elif last_completed and last_completed.end_time:
            last_end_time = last_completed.end_time
        else:
            last_end_time = None

        return Response({
            'machine': MachineLookupSerializer(machine).data,
            'machines': MachineLookupSerializer(machines, many=True).data,
            'running': MachineScheduleBoardSerializer(running).data if running else None,
            'queue': MachineScheduleBoardSerializer(queue, many=True).data,
            'completed': MachineScheduleBoardSerializer(completed, many=True).data,
            'completed_count': completed_count,
            'idle_reasons': IdleTimeSerializer(idle_reasons, many=True).data,
            'downtime_reasons': IdleTimeSerializer(downtime_reasons, many=True).data,
            'pending_count': queue.filter(schedule_type='Production', status='Pending').count(),
            'idle_count': queue.filter(schedule_type='Idle').count(),
            'role': role,
            'is_manager': role == 'manager',
            'is_supervisor': role == 'supervisor',
            'is_operator': role == 'operator',
            'is_viewer': role == 'viewer',
            'last_end_time': last_end_time,
            'running_start_time': running.start_time if running else None,
        })


class ReorderQueueView(APIView):
    """Mirrors reorder_queue() -- manager/supervisor only."""
    permission_classes = [IsPlanningUser]

    def post(self, request, machine_id):
        machine = get_object_or_404(Machine, pk=machine_id)
        require_manager_or_supervisor(request.user)
        offset = 50000
        with transaction.atomic():
            for item in request.data:
                MachineSchedule.objects.filter(
                    pk=item['id'], machine=machine, queue_position__gt=0,
                ).update(queue_position=item['queue_position'] + offset)
            for item in request.data:
                MachineSchedule.objects.filter(pk=item['id'], machine=machine).update(
                    queue_position=item['queue_position'],
                )
        recalculate_timeline(machine)
        return Response({'status': 'ok'})


class AddIdleSlotView(APIView):
    """Mirrors add_idle_slot() -- manager/supervisor only."""
    permission_classes = [IsPlanningUser]

    def post(self, request, machine_id):
        machine = get_object_or_404(Machine, pk=machine_id)
        require_manager_or_supervisor(request.user)

        idle_reason = get_object_or_404(IdleTime, pk=request.data.get('idle_reason_id'))
        hours = int(request.data.get('hours', 0))
        mins = int(request.data.get('mins', 0))
        insert_after = int(request.data.get('insert_after', -1))
        notes = request.data.get('notes', '')
        duration = timedelta(hours=hours, minutes=mins)

        with transaction.atomic():
            if insert_after >= 0:
                new_position = insert_after + 1
                offset = 50000
                MachineSchedule.objects.filter(machine=machine, queue_position__gt=insert_after).update(
                    queue_position=F('queue_position') + offset,
                )
                MachineSchedule.objects.filter(machine=machine, queue_position__gt=offset).update(
                    queue_position=F('queue_position') - offset + 1,
                )
            else:
                last = MachineSchedule.objects.filter(
                    machine=machine, queue_position__gt=0,
                ).order_by('-queue_position').first()
                new_position = (last.queue_position + 1) if last else 1

            schedule = MachineSchedule.objects.create(
                machine=machine, schedule_type='Idle', idle_reason=idle_reason, idle_notes=notes,
                estimated_duration=duration, queue_position=new_position, status='Pending',
                createdby=request.user,
            )

        recalculate_timeline(machine)
        return Response({'status': 'ok', 'id': schedule.id, 'queue_position': schedule.queue_position})
