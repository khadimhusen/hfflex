from django.core.management.base import BaseCommand
from django.db import transaction
from crm.models import Account
from ._import_utils import (
    resolve_owner, clean_str, clean_decimal, clean_datetime, read_export, add_common_arguments,
    resolve_edit_cutoff, edited_since, set_created_at, mark_synced, mark_kept, log_missing_from_export, finish,
)


class Command(BaseCommand):
    help = 'Imports Accounts from a Zoho export (.xlsx or .csv)'

    def add_arguments(self, parser):
        add_common_arguments(parser, 'Path to Accounts_*.xlsx / .csv')

    @transaction.atomic
    def handle(self, *args, **options):
        df = read_export(options['file'])
        cutoff, cutoff_source = resolve_edit_cutoff('import_accounts', Account, options['edited_after'])
        self.stdout.write(f'Keeping CRM edits made after: {cutoff or "n/a"} ({cutoff_source})')
        log, seen = [], []
        created, updated, kept, skipped = 0, 0, 0, 0

        for _, row in df.iterrows():
            zoho_id = clean_str(row.get('Record Id'))
            name = clean_str(row.get('Account Name'))
            row_context = f'Account Record Id={zoho_id}, Name={name}'

            if not zoho_id:
                log.append(f'SKIPPED — no Record Id — {row_context}')
                skipped += 1
                continue
            seen.append(zoho_id)

            if not name:
                log.append(f'SKIPPED — no Account Name — {row_context}')
                skipped += 1
                continue

            existing = Account.objects.filter(zoho_record_id=zoho_id).first()
            zoho_created = clean_datetime(row.get('Created Time'))
            if edited_since(existing, cutoff):
                log.append(f'KEPT — edited in CRM after last import — {row_context} '
                           f'(changed {existing.updated_at:%Y-%m-%d %H:%M})')
                set_created_at(Account, existing.pk, zoho_created)
                mark_kept(Account, existing, cutoff)
                kept += 1
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
            set_created_at(Account, obj.pk, zoho_created)
            mark_synced(Account, obj.pk)
            created += was_created
            updated += not was_created

        missing = log_missing_from_export(Account, seen, log)
        summary = (f'Accounts — created: {created}, updated: {updated}, kept (edited in CRM): {kept}, '
                   f'skipped: {skipped}, in CRM but not in export: {missing}')
        finish(self, 'import_accounts', log, summary, options)
