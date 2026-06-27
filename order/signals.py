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
        # Evaluate queryset BEFORE atomic block
        schedules = list(MachineSchedule.objects.filter(
            jobprocess__job=instance,
            status='Pending',
            queue_position__gt=0,
        ).select_related('machine'))

        machines = set()

        with transaction.atomic():
            for schedule in schedules:
                machine = schedule.machine

                # Lock all rows on this machine
                MachineSchedule.objects.select_for_update().filter(
                    machine=machine
                ).values('id')

                # Re-fetch current position — it may have changed in previous iteration
                current = MachineSchedule.objects.filter(pk=schedule.pk).values('queue_position').first()
                if not current or current['queue_position'] <= 0:
                    continue  # already moved or completed
                old_pos = current['queue_position']

                # Step 1 — move THIS schedule to very high temp position
                MachineSchedule.objects.filter(pk=schedule.pk).update(
                    queue_position=99999
                )

                # Pass A — shift rows above old_pos up to 50000+ range
                MachineSchedule.objects.filter(
                    machine=machine,
                    queue_position__gt=old_pos,
                    queue_position__lt=99999,
                ).update(queue_position=F('queue_position') + 50000)

                # Pass B — shift back down to fill gap
                MachineSchedule.objects.filter(
                    machine=machine,
                    queue_position__gt=50000,
                    queue_position__lt=99999,
                ).update(queue_position=F('queue_position') - 50001)

                # Step 3 — find new end of queue
                last = (
                    MachineSchedule.objects
                    .filter(machine=machine, queue_position__gt=0, queue_position__lt=99999)
                    .order_by('-queue_position')
                    .first()
                )
                new_pos = (last.queue_position + 1) if last else 1

                # Step 4 — move to end as Hold
                MachineSchedule.objects.filter(pk=schedule.pk).update(
                    status='Hold',
                    queue_position=new_pos,
                )

                machines.add(machine)
        # Recalculate OUTSIDE atomic — no locks held
        for machine in machines:
            recalculate_timeline(machine)

    elif job_status in RELEASE_STATUSES:
        schedules = list(MachineSchedule.objects.filter(
            jobprocess__job=instance,
            status='Hold',
            queue_position__gt=0,
        ).select_related('machine'))

        machines = set()

        with transaction.atomic():
            # Lock first
            machine_ids = [s.machine_id for s in schedules]
            MachineSchedule.objects.select_for_update().filter(
                machine_id__in=machine_ids
            ).values('id')

            MachineSchedule.objects.filter(
                jobprocess__job=instance,
                status='Hold',
                queue_position__gt=0,
            ).update(status='Pending')

            for schedule in schedules:
                machines.add(schedule.machine)

        for machine in machines:
            recalculate_timeline(machine)