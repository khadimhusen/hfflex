from django.core.management.base import BaseCommand, CommandError

from company.models import Company, default_company
from purchase.models import Po


class Command(BaseCommand):
    help = (
        'Give every purchase order that has no buyer one -- the default company, or --company. '
        'Normally `migrate` already did this for existing orders; this is for a server where the '
        'default company did not exist yet when it ran. Orders that already have a buyer are never touched.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--company', help='short name of the company to use instead of the default')
        parser.add_argument('--dry-run', action='store_true', help='show the count, change nothing')

    def handle(self, *args, **options):
        if options['company']:
            company = Company.objects.filter(short_name=options['company']).first()
            if company is None:
                raise CommandError(f"No company with short name {options['company']!r}.")
        else:
            company = default_company()
            if company is None:
                raise CommandError('There is no default company yet -- run seed_companies first.')

        orders = Po.objects.filter(buyer__isnull=True)
        count = orders.count()
        if options['dry_run']:
            self.stdout.write(f'{count} purchase orders have no buyer; would set them to {company.name}.')
            return
        orders.update(buyer=company)
        self.stdout.write(self.style.SUCCESS(f'Set {count} purchase orders to {company.name}.'))
