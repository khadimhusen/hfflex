import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from crm.models import Account
from ._import_utils import resolve_owner, clean_str, clean_decimal, write_log_file

class Command(BaseCommand):
    help = 'Imports Accounts from a Zoho Excel export'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, required=True, help='Path to Accounts_*.xlsx')

    @transaction.atomic
    def handle(self, *args, **options):
        df = pd.read_excel(options['file'])
        log = []
        created, updated, skipped = 0, 0, 0

        for _, row in df.iterrows():
            zoho_id = clean_str(row.get('Record Id'))
            name = clean_str(row.get('Account Name'))
            row_context = f'Account Record Id={zoho_id}, Name={name}'

            if not name:
                log.append(f'SKIPPED — no Account Name — {row_context}')
                skipped += 1
                continue

            owner = resolve_owner(row.get('Account Owner'), log, row_context)
            if owner is None:
                log.append(f'SKIPPED — no matching owner — {row_context}')
                skipped += 1
                continue

            obj, was_created = Account.objects.update_or_create(
                zoho_record_id=zoho_id,
                defaults={
                    'name': name,
                    'account_number': clean_str(row.get('Account Number'), 50),
                    'phone': clean_str(row.get('Phone'), 30),
                    'billing_street': clean_str(row.get('Billing Street'), 255),
                    'billing_city': clean_str(row.get('Billing City'), 100),
                    'billing_state': clean_str(row.get('Billing State'), 100),
                    'billing_country': clean_str(row.get('Billing Country'), 100),
                    'billing_code': clean_str(row.get('Billing Code'), 20),
                    'website': clean_str(row.get('Website'), 200),
                    'industry': clean_str(row.get('Industry'), 100),
                    'annual_revenue': clean_decimal(row.get('Annual Revenue')),
                    'enquiry_notes': clean_str(row.get('Description')),
                    'owner': owner,
                },
            )
            created += was_created
            updated += not was_created

        self.stdout.write(self.style.SUCCESS(
            f'Accounts — created: {created}, updated: {updated}, skipped: {skipped}'
        ))
        if log:
            self.stdout.write(self.style.WARNING(f'\n{len(log)} issues:'))
            for line in log:
                self.stdout.write(f'  {line}')

        summary = f'Accounts — created: {created}, updated: {updated}, skipped: {skipped}'
        self.stdout.write(self.style.SUCCESS(summary))

        log_path = write_log_file('import_accounts', log, summary)
        self.stdout.write(f'Full log written to: {log_path}')