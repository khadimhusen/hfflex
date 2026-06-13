from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.db.models import F
from datetime import timedelta

from order.models import JobProcess
from itemmaster.models import ItemProcess
from .models import MachineSchedule, ProductionTask
from .utils import recalculate_timeline
from .choices import HOLD_STATUSES, RELEASE_STATUSES


@receiver(post_save, sender=JobProcess)
def create_schedule_on_jobprocess(sender, instance, created, **kwargs):
    if not created:
        return

    print(f"Signal fired — JobProcess id={instance.id} created={created}")

    try:
        item_process = ItemProcess.objects.filter(
            itemmaster=instance.job.itemmaster,
            process=instance.process,
            process_count=instance.process_count,
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

    print(f"Proceeding — machine={machine}, speed={item_process.speed}")

    speed            = item_process.speed or machine.mode_speed or 60
    qty              = float(instance.qty or 0)
    running_mins     = round(qty / speed) if speed and qty else 30
    running_duration = timedelta(minutes=running_mins)
    tasks            = machine.tasks.all()
    color_count      = instance.job.itemmaster.itemcolors.count() or 1

    # Determine initial status based on job status
    from planning.constants import HOLD_STATUSES
    job_status     = instance.job.jobstatus
    initial_status = 'Hold' if job_status in HOLD_STATUSES else 'Pending'

    makeready_mins = sum(
        t.duration * t.persons_required * (color_count if t.qty_from_colors else 1)
        for t in tasks if t.category == 'Makeready'
    )
    breakdown_mins = sum(
        t.duration * t.persons_required * (color_count if t.qty_from_colors else 1)
        for t in tasks if t.category == 'Breakdown'
    )

    makeready_duration = timedelta(minutes=makeready_mins)
    downtime_duration = timedelta(minutes=breakdown_mins)
    estimated_duration = makeready_duration + running_duration + downtime_duration

    last = (
        MachineSchedule.objects
        .for_machine(machine)
        .pending()
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
        status             = initial_status,
        makeready_duration = makeready_duration,
        running_duration   = running_duration,
        downtime_duration = downtime_duration,
        estimated_duration = estimated_duration,
        queue_position     = next_position,
        createdby          = instance.createdby,
    )

    production_tasks = [
        ProductionTask(
            machine_schedule = schedule,
            task             = t,
            time_per_task    = t.duration,
            qty              = color_count if t.qty_from_colors else 1,
        )
        for t in tasks
    ]
    if production_tasks:
        ProductionTask.objects.bulk_create(production_tasks)

    recalculate_timeline(machine)
    print(f"MachineSchedule created — id={schedule.id}, position={next_position}")


@receiver(post_save, sender=MachineSchedule)
def recalculate_on_schedule_change(sender, instance, created, **kwargs):
    if instance.queue_position is None:
        return
    if created:
        return
    recalculate_timeline(instance.machine)


@receiver(post_save, sender=ProductionTask)
def recalculate_on_task_change(sender, instance, created, **kwargs):
    print(f"recalculate_on_task_change fired — ProductionTask id={instance.id}")

    schedule = MachineSchedule.objects.select_related('machine').get(
        pk=instance.machine_schedule_id
    )

    tasks = schedule.productiontasks.select_related('task').all()

    makeready_mins = sum(
        pt.effective_duration for pt in tasks if pt.task.category == 'Makeready'
    )
    breakdown_mins = sum(
        pt.effective_duration for pt in tasks if pt.task.category == 'Breakdown'
    )

    makeready_duration = timedelta(minutes=makeready_mins)
    downtime_duration = timedelta(minutes=breakdown_mins)
    estimated_duration = (
        makeready_duration +
        (schedule.running_duration or timedelta(0)) +
        downtime_duration
    )

    MachineSchedule.objects.filter(pk=schedule.pk).update(
        makeready_duration = makeready_duration,
        downtime_duration = downtime_duration,
        estimated_duration = estimated_duration,
    )

    recalculate_timeline(schedule.machine)