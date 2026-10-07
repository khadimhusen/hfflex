from django.core.management.base import BaseCommand
from django.db import transaction

from company.models import Company
from customer.models import Address, Customer


class Command(BaseCommand):
    help = (
        'Link each company to the customer record that stands for it (where its purchase orders are '
        'delivered). Finds the customer by GSTIN, then by name; with --create, makes one -- with the '
        "company's address as its delivery address -- when there is none. Companies that are already "
        'linked are left alone. Linking by hand in the admin does the same thing.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--create', action='store_true',
                            help='create the customer (and address) for a company that has none')
        parser.add_argument('--dry-run', action='store_true', help='say what would happen, change nothing')

    def handle(self, *args, **options):
        create, dry = options['create'], options['dry_run']
        for company in Company.objects.filter(customer__isnull=True).order_by('name'):
            customer = None
            if company.gstin:
                customer = Customer.objects.filter(gst=company.gstin).first()
            customer = customer or Customer.objects.filter(name=company.name.upper()).first()
            if customer is None and company.receiving_customer is not None:
                customer = company.receiving_customer      # H F Flex's legacy record, found by name
            verb = 'link to existing customer' if customer else ('create a customer for' if create else None)
            if verb is None:
                self.stdout.write(f'{company.name}: no matching customer -- re-run with --create, '
                                  f'or pick one in the admin.')
                continue
            if dry:
                self.stdout.write(f'{company.name}: would {verb} {customer or company.name}.')
                continue
            with transaction.atomic():
                if customer is None:
                    customer = Customer.objects.create(
                        name=company.name, gst=company.gstin or None, email=company.email or None,
                        is_customer=False, is_supplier=False)
                    if company.address_line1 or company.address_line2:
                        Address.objects.create(customer=customer, addname='Factory',
                                               add1=company.address_line1, add2=company.address_line2,
                                               phone=company.phone[:16])
                company.customer = customer
                company.save(update_fields=['customer', 'edited'])
            self.stdout.write(self.style.SUCCESS(f'{company.name}: linked to {customer.name}.'))
