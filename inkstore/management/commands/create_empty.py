from django.core.management.base import BaseCommand
from inkstore.models import MixedInk

class Command(BaseCommand):
    help = 'Create empty record'


    def handle(self, *args, **options):

        for i in range(1000):
            MixedInk.objects.update_or_create(id=i+1,l_nw = 0,a_nw=0,b_nw=0,l_ww=0,a_ww=0,b_ww=0)

        self.stdout.write(self.style.SUCCESS(f'record created'))



