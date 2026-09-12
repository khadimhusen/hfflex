from django.core.management.base import BaseCommand
from django.db import transaction
from crm.models import Account, Contact
from ._import_utils import (
    resolve_owner, clean_str, clean_datetime, read_export, add_common_arguments,
    resolve_edit_cutoff, edited_since, set_created_at, mark_synced, mark_kept, log_missing_from_export, finish,
)


class Command(BaseCommand):
    help = 'Imports Contacts from a Zoho export (.xlsx or .csv)'

    def add_arguments(self, parser):
        add_common_arguments(parser, 'Path to Contacts_*.xlsx / .csv')

    @transaction.atomic
    def handle(self, *args, **options):
        df = read_export(options['file'])
        cutoff, cutoff_source = resolve_edit_cutoff('import_contacts', Contact, options['edited_after'])
        self.stdout.write(f'Keeping CRM edits made after: {cutoff or "n/a"} ({cutoff_source})')
        log, seen = [], []
        created, updated, kept, skipped = 0, 0, 0, 0

        for _, row in df.iterrows():
            zoho_id = clean_str(row.get('Record Id'))
            last_name = clean_str(row.get('Last Name'))
            row_context = f'Contact Record Id={zoho_id}, {last_name}'

            if not zoho_id:
                log.append(f'SKIPPED — no Record Id — {row_context}')
                skipped += 1
                continue
            seen.append(zoho_id)

            if not last_name:
                log.append(f'SKIPPED — no Last Name — {row_context}')
                skipped += 1
                continue

            existing = Contact.objects.filter(zoho_record_id=zoho_id).first()
            zoho_created = clean_datetime(row.get('Created Time'))
            if edited_since(existing, cutoff):
                log.append(f'KEPT — edited in CRM after last import — {row_context} '
                           f'(changed {existing.updated_at:%Y-%m-%d %H:%M})')
                set_created_at(Contact, existing.pk, zoho_created)
                mark_kept(Contact, existing, cutoff)
                kept += 1
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
            set_created_at(Contact, obj.pk, zoho_created)
            mark_synced(Contact, obj.pk)
            created += was_created
            updated += not was_created

        missing = log_missing_from_export(Contact, seen, log)
        summary = (f'Contacts — created: {created}, updated: {updated}, kept (edited in CRM): {kept}, '
                   f'skipped: {skipped}, in CRM but not in export: {missing}')
        finish(self, 'import_contacts', log, summary, options)
