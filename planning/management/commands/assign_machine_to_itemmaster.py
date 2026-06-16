# planning/management/commands/assign_machine_to_itemprocess.py

from django.core.management.base import BaseCommand
from itemmaster.models import ItemProcess, Machine, Process


class Command(BaseCommand):
    help = 'Assign default machines to ItemProcess records where machine is null'

    def handle(self, *args, **kwargs):

        PROCESS_MACHINE_MAP = {
            'Printing'  : 'PRINTING-1',
            'Lamination': 'LAMINATION-1',
            'Slitting'  : 'SLITTING-1',
            'Pouching'  : 'POUCHING-1',
        }

        total_updated = 0

        for process_name, machine_name in PROCESS_MACHINE_MAP.items():
            try:
                machine = Machine.objects.get(machinename=machine_name)
            except Machine.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Machine not found: {machine_name}")
                )
                continue

            try:
                process = Process.objects.get(process=process_name)
            except Process.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Process not found: {process_name}")
                )
                continue

            count = ItemProcess.objects.filter(
                process       = process,
                machine__isnull = True
            ).update(machine=machine)

            total_updated += count
            self.stdout.write(
                self.style.SUCCESS(
                    f"{process_name} → {machine_name}: {count} updated"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(f"\nTotal updated: {total_updated}")
        )
