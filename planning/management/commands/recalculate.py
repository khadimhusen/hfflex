from planning.models import MachineSchedule
from planning.utils import recalculate_timeline
from itemmaster.models import Machine
from datetime import timedelta
from django.core.management.base import BaseCommand



class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        # Get all pending and hold pouching schedules
        schedules = MachineSchedule.objects.filter(
            machine__machinename__icontains='POUCHING',
            queue_position__gt=0,  # pending and hold only
        ).select_related('machine')

        print(f"Found {schedules.count()} schedules to update")

        updated = 0

        for s in schedules:
            speed = s.speed or 60
            qty   = float(s.qty or 0)

            new_running_mins = round(qty / speed) if speed and qty else 0
            new_running_dur  = timedelta(minutes=new_running_mins)
            new_estimated    = (
                (s.makeready_duration or timedelta(0)) +
                new_running_dur +
                (s.downtime_duration  or timedelta(0))
            )

            MachineSchedule.objects.filter(pk=s.pk).update(
                running_duration   = new_running_dur,
                estimated_duration = new_estimated,
            )
            print(f"Schedule id={s.id} qty={s.qty} speed={speed} running={new_running_dur}")
            updated += 1

        print(f"\nUpdated: {updated}")

        # Recalculate timeline
        pouching = Machine.objects.filter(machinename__icontains='POUCHING').first()
        if pouching:
            recalculate_timeline(pouching)
            print("Timeline recalculated")