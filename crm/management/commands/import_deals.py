import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from crm.models import Account, Contact, Pipeline, DealStage, Deal
from ._import_utils import resolve_owner, clean_str, clean_decimal, write_log_file

SKIP_PIPELINES = {'standard'}  # dropped — Zoho's unused generic default


class Command(BaseCommand):
    help = 'Imports Deals from a Zoho Excel export'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, required=True, help='Path to Deals_*.xlsx')

    @transaction.atomic
    def handle(self, *args, **options):
        df = pd.read_excel(options['file'])
        log = []
        created, updated, skipped = 0, 0, 0

        # Pre-build a case-insensitive stage lookup per pipeline, since
        # Zoho's Stage column is uppercase ("DATA SEARCH") but our seeded
        # DealStageName rows are human-cased ("Data Search").
        stage_lookup = {}
        for stage in DealStage.objects.select_related('pipeline', 'dealstagename'):
            key = (stage.pipeline.name.strip().lower(), stage.dealstagename.name.strip().lower())
            stage_lookup[key] = stage

        for _, row in df.iterrows():
            zoho_id = clean_str(row.get('Record Id'))
            name = clean_str(row.get('Deal Name'))
            pipeline_raw = clean_str(row.get('Pipeline'))
            stage_raw = clean_str(row.get('Stage'))
            row_context = f'Deal Record Id={zoho_id}, Name={name}'

            if 'standard' in pipeline_raw.strip().lower():
                log.append(f'SKIPPED — Standard pipeline (dropped) — {row_context}')
                skipped += 1
                continue

            key = (pipeline_raw.strip().lower(), stage_raw.strip().lower())
            stage = stage_lookup.get(key)
            if stage is None:
                log.append(f'UNMATCHED PIPELINE/STAGE "{pipeline_raw}" / "{stage_raw}" — {row_context}')
                skipped += 1
                continue

            owner = resolve_owner(row.get('Deal Owner'), log, row_context)
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

            contact = None
            contact_zoho_id = clean_str(row.get('Contact Name.id'))
            if contact_zoho_id:
                contact = Contact.objects.filter(zoho_record_id=contact_zoho_id).first()
                if contact is None:
                    log.append(f'UNMATCHED CONTACT ref "{contact_zoho_id}" — {row_context}')

            closing_date = row.get('Closing Date')
            closing_date = None if pd.isna(closing_date) else closing_date

            obj, was_created = Deal.objects.update_or_create(
                zoho_record_id=zoho_id,
                defaults={
                    'name': name,
                    'pipeline': stage.pipeline,
                    'stage': stage,
                    'account': account,
                    'contact': contact,
                    'amount': clean_decimal(row.get('Amount')),
                    'deal_type': clean_str(row.get('Type'), 30),
                    'city': clean_str(row.get('City'), 100),
                    'lost_reason': clean_str(row.get('Reason For Loss'), 100),
                    'lead_source': clean_str(row.get('Lead Source'), 50),
                    'closing_date': closing_date,
                    'owner': owner,
                    'description': clean_str(row.get('Description')),
                },
            )
            created += was_created
            updated += not was_created

        self.stdout.write(self.style.SUCCESS(
            f'Deals — created: {created}, updated: {updated}, skipped: {skipped}'
        ))
        if log:
            self.stdout.write(self.style.WARNING(f'\n{len(log)} issues:'))
            for line in log:
                self.stdout.write(f'  {line}')
        summary = f'Deals — created: {created}, updated: {updated}, skipped: {skipped}'
        self.stdout.write(self.style.SUCCESS(summary))

        log_path = write_log_file('import_deals', log, summary)
        self.stdout.write(f'Full log written to: {log_path}')
