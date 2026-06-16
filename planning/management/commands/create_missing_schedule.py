from django.core.management.base import BaseCommand
from order.models import JobProcess
from itemmaster.models import ItemProcess
from planning.models import MachineSchedule, ProductionTask
from planning.choices import HOLD_STATUSES
from planning.utils import recalculate_timeline
from datetime import timedelta


class Command(BaseCommand):
    help = 'Create MachineSchedule for pending JobProcess records that have no schedule'

    def handle(self, *args, **kwargs):
        # Find JobProcess with no schedule, job pending, process pending
        jobprocesses = JobProcess.objects.filter(
            job__jobstatus='Pending',
            status='Pending',
            schedules__isnull=True,  # no MachineSchedule yet
        ).select_related(
            'job__itemmaster', 'process'
        ).distinct()

        self.stdout.write(f"Found {jobprocesses.count()} JobProcess records without schedule")

        created_count  = 0
        skipped_count  = 0
        machines_seen  = set()

        for instance in jobprocesses:
            # Resolve ItemProcess template
            try:
                item_process = ItemProcess.objects.filter(
                    itemmaster     = instance.job.itemmaster,
                    process        = instance.process,
                    process_count  = instance.process_count,
                ).order_by('-created').first()

                if not item_process:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Skip JP#{instance.id} — no ItemProcess template found"
                        )
                    )
                    skipped_count += 1
                    continue

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Skip JP#{instance.id} — error: {e}")
                )
                skipped_count += 1
                continue

            machine = item_process.machine
            if not machine:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skip JP#{instance.id} — no machine on ItemProcess"
                    )
                )
                skipped_count += 1
                continue

            # Determine initial status
            job_status     = instance.job.jobstatus
            initial_status = 'Hold' if job_status in HOLD_STATUSES else 'Pending'

            # Speed and durations
            speed        = item_process.speed or machine.mode_speed or 60
            qty          = float(instance.qty or 0)
            running_mins = round(qty / speed) if speed and qty else 30
            running_dur  = timedelta(minutes=running_mins)

            tasks       = machine.tasks.all()
            color_count = instance.job.itemmaster.itemcolors.count() or 1

            makeready_mins = sum(
                t.duration * t.persons_required * (color_count if t.qty_from_colors else 1)
                for t in tasks if t.category == 'Makeready'
            )
            downtime_mins = sum(
                t.duration * t.persons_required * (color_count if t.qty_from_colors else 1)
                for t in tasks if t.category == 'Breakdown'
            )

            makeready_dur  = timedelta(minutes=makeready_mins)
            downtime_dur   = timedelta(minutes=downtime_mins)
            estimated_dur  = makeready_dur + running_dur + downtime_dur

            # Queue position
            last = (
                MachineSchedule.objects
                .filter(machine=machine, queue_position__gt=0)
                .order_by('-queue_position')
                .first()
            )
            next_position = (last.queue_position + 1) if last else 1

            # Create MachineSchedule
            schedule = MachineSchedule.objects.create(
                schedule_type      = 'Production',
                jobprocess         = instance,
                machine            = machine,
                qty                = instance.qty,
                unit               = instance.unit,
                speed              = speed,
                status             = initial_status,
                makeready_duration = makeready_dur,
                running_duration   = running_dur,
                downtime_duration  = downtime_dur,
                estimated_duration = estimated_dur,
                queue_position     = next_position,
                createdby          = instance.createdby,
            )

            # Create ProductionTasks
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

            machines_seen.add(machine)
            created_count += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created schedule for JP#{instance.id} — "
                    f"{instance.job} / {instance.process} → {machine}"
                )
            )

        # Recalculate timeline for all affected machines
        for machine in machines_seen:
            recalculate_timeline(machine)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone — Created: {created_count}, Skipped: {skipped_count}"
            )
        )