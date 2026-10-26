from django.core.management.base import BaseCommand

from customer.models import Customer

DEFAULT_NAMES = ['GODOWN-1', 'GODOWN-2', 'PRODUCTION']


class Command(BaseCommand):
    help = (
        'Tick "Cylinder location" on the customer records that are our own storage places '
        '(GODOWN-1, GODOWN-2, PRODUCTION by default; --name adds more). Run once after the '
        'is_cylinder_location column is added. Safe to re-run; matches names exactly and never unticks.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--name', action='append', default=[],
                            help='another exact customer name to tick (repeatable)')
        parser.add_argument('--dry-run', action='store_true', help='say what would change, change nothing')

    def handle(self, *args, **options):
        names = DEFAULT_NAMES + [n.strip().upper() for n in options['name']]
        for name in names:
            customer = Customer.objects.filter(name=name).first()
            if customer is None:
                self.stdout.write(self.style.WARNING(f'{name}: no customer with this exact name -- skipped.'))
            elif customer.is_cylinder_location:
                self.stdout.write(f'{name}: already ticked.')
            elif options['dry_run']:
                self.stdout.write(f'{name}: would tick.')
            else:
                Customer.objects.filter(pk=customer.pk).update(is_cylinder_location=True)
                self.stdout.write(self.style.SUCCESS(f'{name}: ticked.'))
