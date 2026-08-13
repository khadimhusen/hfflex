import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from crm.models import Account, Contact
from ._import_utils import resolve_owner, clean_str,write_log_file


class Command(BaseCommand):
    help = 'Imports Contacts from a Zoho Excel export'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, required=True, help='Path to Contacts_*.xlsx')

    @transaction.atomic
    def handle(self, *args, **options):
        df = pd.read_excel(options['file'])
        log = []
        created, updated, skipped = 0, 0, 0

        for _, row in df.iterrows():
            zoho_id = clean_str(row.get('Record Id'))
            last_name = clean_str(row.get('Last Name'))
            row_context = f'Contact Record Id={zoho_id}, {last_name}'

            if not last_name:
                log.append(f'SKIPPED — no Last Name — {row_context}')
                skipped += 1
                continue

            owner = resolve_owner(row.get('Contact Owner'), log, row_context)
            if owner is None:
                log.append(f'SKIPPED — no matching owner — {row_context}')
                skipped += 1
                continue

            account = None
            account_zoho_id = clean_str(row.get('Account Name.id'))
            if account_zoho_id:
                account = Account.objects.filter(zoho_record_id=account_zoho_id).first()
                if account is None:
                    log.append(f'UNMATCHED ACCOUNT ref "{account_zoho_id}" — {row_context}')

            obj, was_created = Contact.objects.update_or_create(
                zoho_record_id=zoho_id,
                defaults={
                    'first_name': clean_str(row.get('First Name'), 100),
                    'last_name': last_name,
                    'account': account,
                    'title': clean_str(row.get('Title'), 100),
                    'email': clean_str(row.get('Email'), 254),
                    'phone': clean_str(row.get('Phone'), 30),
                    'mobile': clean_str(row.get('Mobile'), 30),
                    'mailing_street': clean_str(row.get('Mailing Street'), 255),
                    'mailing_city': clean_str(row.get('Mailing City'), 100),
                    'mailing_state': clean_str(row.get('Mailing State'), 100),
                    'mailing_country': clean_str(row.get('Mailing Country'), 100),
                    'mailing_zip': clean_str(row.get('Mailing Zip'), 20),
                    'lead_source': clean_str(row.get('Lead Source'), 50),
                    'description': clean_str(row.get('Description')),
                    'owner': owner,
                },
            )
            created += was_created
            updated += not was_created

        self.stdout.write(self.style.SUCCESS(
            f'Contacts — created: {created}, updated: {updated}, skipped: {skipped}'
        ))
        if log:
            self.stdout.write(self.style.WARNING(f'\n{len(log)} issues:'))
            for line in log:
                self.stdout.write(f'  {line}')
        summary = f'Contacts - created: {created}, updated: {updated}, skipped: {skipped}'
        self.stdout.write(self.style.SUCCESS(summary))

        log_path = write_log_file('import_contacts', log, summary)
        self.stdout.write(f'Full log written to: {log_path}')