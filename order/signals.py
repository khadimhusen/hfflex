from django.db.models.signals import post_save, post_delete, pre_save
from .models import JobMaterial, Job, JobChangeLog

from production.models import JobMaterialStatus
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from django.db.models import F

from planning.models import MachineSchedule
from planning.utils import recalculate_timeline
from planning.choices import HOLD_STATUSES, RELEASE_STATUSES


@receiver(post_save, sender=JobMaterial)
def jobmaterial_is_created(sender, instance, created, **kwargs):
    if not created:
        instance.job.save()


@receiver(post_save, sender=JobMaterialStatus)
def jobmaterialstatus_is_updated(sender, instance, **kwargs):
    instance.jobmaterial.save()
    instance.allote.save()


@receiver(post_delete, sender=JobMaterialStatus)
def jobmaterialstatus_is_delete(sender, instance, **kwargs):
    instance.jobmaterial.save()
    instance.allote.save()


# Fields you actually want to track (skip auto_now, audit junk)
TRACKED_FIELDS = [
    "prejob",
    "joborder",
    "itemmaster",
    "quantity",
    "rate",
    "jobstatus",
    "jobremark",
    "itemname",
    "replength",
    "openwidth",
    "slit_size",
    "no_of_repeat",
    "no_of_ups",
    "cyl_length",
    "cyl_circum",
    "pouch_type",
    "supply_form",
    "film_size",
    "remark",
    "unwind_direction",

]


@receiver(pre_save, sender=Job)
def capture_job_changes(sender, instance, **kwargs):
    # New record — no old row to compare
    if not instance.pk:
        instance._pending_changes = []
        instance._is_new = True
        return

    try:
        old = Job.objects.get(pk=instance.pk)
    except Job.DoesNotExist:
        instance._pending_changes = []
        instance._is_new = True
        return

    changes = []
    for field in TRACKED_FIELDS:
        old_val = getattr(old, field)
        new_val = getattr(instance, field)
        if old_val != new_val:
            changes.append({
                'field': field,
                'old': str(old_val) if old_val is not None else None,
                'new': str(new_val) if new_val is not None else None,
            })

    instance._pending_changes = changes
    instance._is_new = False


@receiver(post_save, sender=Job)
def write_job_changes(sender, instance, created, **kwargs):


    if created:
        JobChangeLog.objects.create(
            job=instance,
            field_name='__created__',
            old_value=None,
            new_value=None,
            changed_by=instance.editedby,
            action='create',
        )
        return

    changes = getattr(instance, '_pending_changes', [])
    if not changes:
        return

    logs = [
        JobChangeLog(
            job=instance,
            field_name=c['field'],
            old_value=c['old'],
            new_value=c['new'],
            changed_by=instance.editedby,
            action='update',
        ) for c in changes
    ]
    JobChangeLog.objects.bulk_create(logs)


@receiver(post_save, sender=Job)
def sync_schedule_on_job_status(sender, instance, created, **kwargs):
    if created:
        return

    job_status = instance.jobstatus

    if job_status in HOLD_STATUSES:
        schedules = MachineSchedule.objects.filter(
            jobprocess__job=instance,
            status='Pending',
            queue_position__gt=0,
        ).select_related('machine')

        with transaction.atomic():
            for schedule in schedules:
                machine = schedule.machine
                offset  = 1000
                old_pos = schedule.queue_position

                # Step 1 — move THIS schedule to temp position first
                MachineSchedule.objects.filter(pk=schedule.pk).update(
                    queue_position=offset + 500
                )

                # Step 2 — close gap, skip our temp row
                MachineSchedule.objects.filter(
                    machine=machine,
                    queue_position__gt=old_pos,
                    queue_position__lt=offset
                ).update(queue_position=F('queue_position') + offset)

                MachineSchedule.objects.filter(
                    machine=machine,
                    queue_position__gt=offset,
                    queue_position__lt=offset + 500
                ).update(queue_position=F('queue_position') - offset - 1)

                # Step 3 — find new end of queue
                last = (
                    MachineSchedule.objects
                    .select_for_update()
                    .filter(machine=machine, queue_position__gt=0)
                    .order_by('-queue_position')
                    .first()
                )
                new_pos = (last.queue_position + 1) if last else 1

                # Step 4 — move to end and set Hold
                MachineSchedule.objects.filter(pk=schedule.pk).update(
                    status='Hold',
                    queue_position=new_pos,
                )

                recalculate_timeline(machine)

    elif job_status in RELEASE_STATUSES:
        schedules = MachineSchedule.objects.filter(
            jobprocess__job=instance,
            status='Hold',
            queue_position__gt=0,
        ).select_related('machine')

        machines = set()
        with transaction.atomic():
            schedules.update(status='Pending')
            for schedule in schedules:
                machines.add(schedule.machine)

        for machine in machines:
            recalculate_timeline(machine)