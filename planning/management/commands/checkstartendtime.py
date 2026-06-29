from django.core.management.base import BaseCommand

from planning.models import MachineSchedule

from django.db.models import F

class Command(BaseCommand):
    help = 'Check if start time is less then or equal endtime'



    def handle(self, *args, **kwargs):


        updated = MachineSchedule.objects.filter(
            start_time__isnull=False,
            end_time__isnull=False,
            end_time__lt=F('start_time')
        ).update(end_time=F('start_time'))

        print(f"Fixed {updated} records")