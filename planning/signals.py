from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from datetime import timedelta

from order.models import JobProcess
from itemmaster.models import ItemProcess
from .models import MachineSchedule, ProductionTask
from .utils import recalculate_timeline
from .choices import HOLD_STATUSES


# ------------------------------------------------------------------ #
# Helper                                                               #
# ------------------------------------------------------------------ #
def task_duration_mins(task, qty, persons_assigned):
    """Calculate task duration in minutes respecting person-independence.

    task            : MachineTask instance
    qty             : number of times task is performed
    persons_assigned: persons working on machine

    If persons_required == 0 the task is person-independent —
    duration = qty × duration only, not divided by persons_assigned.
    """
    if task.persons_required == 0:
        return task.duration * qty
    return round((task.duration * task.persons_required * qty) / persons_assigned)


# ------------------------------------------------------------------ #
# Create MachineSchedule when JobProcess is created                   #
# ------------------------------------------------------------------ #
@receiver(post_save, sender=JobProcess)
def create_schedule_on_jobprocess(sender, instance, created, **kwargs):
    if not created:
        return


    try:
        item_process = ItemProcess.objects.filter(
            itemmaster    = instance.job.itemmaster,
            process       = instance.process,
            process_count = instance.process_count,
        ).order_by('-created').first()

        if not item_process:
            print("Exit — no ItemProcess template found")
            return

    except Exception as e:
        print(f"Exit — ItemProcess lookup error: {e}")
        return

    machine = item_process.machine
    if not machine:
        print("Exit — no machine on ItemProcess")
        return


    speed            = item_process.speed or machine.mode_speed or 60
    qty              = float(instance.qty or 0)
    running_mins     = round(qty / speed) if speed and qty else 30
    running_duration = timedelta(minutes=running_mins)
    tasks            = machine.tasks.all()  # MachineTask objects
    color_count      = instance.job.itemmaster.itemcolors.count() or 1
    persons_assigned = machine.default_persons or 2  # use machine default

    job_status     = instance.job.jobstatus
    initial_status = 'Hold' if job_status in HOLD_STATUSES else 'Pending'

    # t is MachineTask — use t directly (not t.task)
    makeready_mins = sum(
        task_duration_mins(
            t,
            color_count if t.default_qty is None else t.default_qty,
            persons_assigned
        )
        for t in tasks if t.category == 'Makeready'
    )
    breakdown_mins = sum(
        task_duration_mins(
            t,
            color_count if t.default_qty is None else t.default_qty,
            persons_assigned
        )
        for t in tasks if t.category == 'Breakdown'
    )

    makeready_duration = timedelta(minutes=makeready_mins)
    downtime_duration  = timedelta(minutes=breakdown_mins)
    estimated_duration = makeready_duration + running_duration + downtime_duration

    with transaction.atomic():
        # Lock machine rows before computing next_position
        MachineSchedule.objects.select_for_update().filter(
            machine=machine
        ).values('id')

        last = (
            MachineSchedule.objects
            .filter(machine=machine, queue_position__gt=0)
            .order_by('-queue_position')
            .first()
        )
        next_position = (last.queue_position + 1) if last else 1

        schedule = MachineSchedule.objects.create(
            schedule_type      = 'Production',
            jobprocess         = instance,
            machine            = machine,
            qty                = instance.qty,
            unit               = instance.unit,
            speed              = speed,
            persons_assigned   = persons_assigned,
            status             = initial_status,
            makeready_duration = makeready_duration,
            running_duration   = running_duration,
            downtime_duration  = downtime_duration,
            estimated_duration = estimated_duration,
            queue_position     = next_position,
            createdby          = instance.createdby,
        )

        # t is MachineTask — use t as FK for task field
        production_tasks = [
            ProductionTask(
                machine_schedule = schedule,
                task             = t,
                time_per_task    = t.duration,
                qty              = color_count if t.default_qty is None else t.default_qty,
            )
            for t in tasks
        ]
        if production_tasks:
            ProductionTask.objects.bulk_create(production_tasks)

    recalculate_timeline(machine)


# ------------------------------------------------------------------ #
# Recalculate timeline when MachineSchedule changes                   #
# ------------------------------------------------------------------ #
@receiver(post_save, sender=MachineSchedule)
def recalculate_on_schedule_change(sender, instance, created, **kwargs):
    if instance.queue_position is None:
        return
    if created:
        return  # create_schedule_on_jobprocess already calls recalculate_timeline
    recalculate_timeline(instance.machine)


# ------------------------------------------------------------------ #
# Recalculate durations when ProductionTask changes                   #
# ------------------------------------------------------------------ #
@receiver(post_save, sender=ProductionTask)
def recalculate_on_task_change(sender, instance, created, **kwargs):

    schedule = MachineSchedule.objects.select_related('machine').get(
        pk=instance.machine_schedule_id
    )

    # tasks here are ProductionTask objects — use t.task for MachineTask attributes
    tasks            = schedule.productiontasks.select_related('task').all()
    persons_assigned = schedule.persons_assigned or 2

    makeready_mins = sum(
        task_duration_mins(t.task, t.qty, persons_assigned)
        for t in tasks if t.task.category == 'Makeready'
    )
    breakdown_mins = sum(
        task_duration_mins(t.task, t.qty, persons_assigned)
        for t in tasks if t.task.category == 'Breakdown'
    )

    makeready_duration = timedelta(minutes=makeready_mins)
    downtime_duration  = timedelta(minutes=breakdown_mins)
    estimated_duration = (
        makeready_duration +
        (schedule.running_duration or timedelta(0)) +
        downtime_duration
    )

    # Use .update() to avoid triggering recalculate_on_schedule_change signal
    MachineSchedule.objects.filter(pk=schedule.pk).update(
        makeready_duration = makeready_duration,
        downtime_duration  = downtime_duration,
        estimated_duration = estimated_duration,
    )

    recalculate_timeline(schedule.machine)