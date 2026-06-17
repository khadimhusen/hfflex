from django.core.management.base import BaseCommand
from planning.models import MachineSchedule
from material.models import Unit


class Command(BaseCommand):

    def handle(self, *args, **kwargs):
        # Get NOS unit
        try:
            nos_unit = Unit.objects.get(unit='NOS.')
        except Unit.DoesNotExist:
            nos_unit = Unit.objects.get(unit='NOS')

        # Get all pending/running pouching schedules with KG unit
        kg_unit_names = ['KG.', 'KG', 'Kg']
        schedules = MachineSchedule.objects.filter(
            machine__machinename__icontains='POUCHING',
            unit__unit__in=kg_unit_names,
            queue_position__gte=-1,
        ).select_related('jobprocess__job', 'unit')

        print(f"Found {schedules.count()} schedules to convert")

        converted = 0
        skipped = 0

        for s in schedules:
            try:
                pouch_per_kg = s.jobprocess.job.pouch_per_kg
                if not pouch_per_kg or pouch_per_kg == 0:
                    print(f"Skip schedule id={s.id} — pouch_per_kg is zero or None")
                    skipped += 1
                    continue

                old_qty = s.qty
                new_qty = round(float(s.qty) * float(pouch_per_kg), 0)

                MachineSchedule.objects.filter(pk=s.pk).update(
                    qty=new_qty,
                    unit=nos_unit,
                )
                print(f"Schedule id={s.id} — {old_qty} KG → {new_qty} NOS")
                converted += 1

            except Exception as e:
                print(f"Skip schedule id={s.id} — error: {e}")
                skipped += 1

        print(f"\nConverted: {converted}, Skipped: {skipped}")
