from django.core.management.base import BaseCommand

from company.linking import find_customer, link_customer
from company.models import Company


class Command(BaseCommand):
    help = (
        'Link each company to the customer record that stands for it (where its purchase orders are '
        'delivered). Finds the customer by GSTIN, then by name; with --create, makes one -- with the '
        "company's address as its delivery address -- when there is none. Companies that are already "
        'linked are left alone. Saving a company in the admin does the same, so this is only needed for '
        'companies that existed before the link did.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--create', action='store_true',
                            help='create the customer (and address) for a company that has none')
        parser.add_argument('--dry-run', action='store_true', help='say what would happen, change nothing')

    def handle(self, *args, **options):
        create, dry = options['create'], options['dry_run']
        for company in Company.objects.filter(customer__isnull=True).order_by('name'):
            existing = find_customer(company)
            if existing is None and not create:
                self.stdout.write(f'{company.name}: no matching customer -- re-run with --create, '
                                  f'or pick one in the admin.')
                continue
            if dry:
                what = f'link to existing customer {existing}' if existing else 'create a customer for it'
                self.stdout.write(f'{company.name}: would {what}.')
                continue
            customer = link_customer(company, create=create)
            self.stdout.write(self.style.SUCCESS(f'{company.name}: linked to {customer.name}.'))
