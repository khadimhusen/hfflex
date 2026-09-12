import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from crm.models import Account, Contact, DealStage, Deal, DealStageHistory
from ._import_utils import (
    resolve_owner, clean_str, clean_decimal, clean_datetime, read_export, add_common_arguments,
    resolve_edit_cutoff, edited_since, set_created_at, mark_synced, mark_kept, log_missing_from_export, finish,
)

SKIP_PIPELINES = {'standard'}  # dropped — Zoho's unused generic default


def sync_stage_entry(deal, old_stage_id, entered_at):
    """Start the deal's stall clock when it really entered its stage in Zoho.

    Stalling is measured from the latest history row for the current stage.
    Without this, an imported deal "entered" its stage on the day of the
    import: nothing stalls on day one, then every deal stalls at once.
    Zoho's export has no stage-entry time, so its Modified Time stands in.

    Only rows the system wrote (changed_by is null) are ever touched, and not
    at all once a person has moved the deal in the CRM.
    """
    if entered_at is None:
        return
    history = DealStageHistory.objects.filter(deal=deal)
    if history.filter(changed_by__isnull=False).exists():
        return

    if old_stage_id is not None and old_stage_id != deal.stage_id:
        entry = DealStageHistory.objects.create(
            deal=deal, from_stage_id=old_stage_id, to_stage_id=deal.stage_id, changed_by=None,
        )
        DealStageHistory.objects.filter(pk=entry.pk).update(changed_at=entered_at)
        return

    current = history.filter(to_stage_id=deal.stage_id)
    if current.exists():
        current.filter(from_stage__isnull=True).update(changed_at=entered_at)
    else:
        entry = DealStageHistory.objects.create(
            deal=deal, from_stage=None, to_stage_id=deal.stage_id, changed_by=None,
        )
        DealStageHistory.objects.filter(pk=entry.pk).update(changed_at=entered_at)


class Command(BaseCommand):
    help = 'Imports Deals from a Zoho export (.xlsx or .csv)'

    def add_arguments(self, parser):
        add_common_arguments(parser, 'Path to Deals_*.xlsx / .csv')

    @transaction.atomic
    def handle(self, *args, **options):
        df = read_export(options['file'])
        cutoff, cutoff_source = resolve_edit_cutoff('import_deals', Deal, options['edited_after'])
        self.stdout.write(f'Keeping CRM edits made after: {cutoff or "n/a"} ({cutoff_source})')
        log, seen = [], []
        created, updated, kept, skipped = 0, 0, 0, 0

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

            if not zoho_id:
                log.append(f'SKIPPED — no Record Id — {row_context}')
                skipped += 1
                continue
            seen.append(zoho_id)

            if 'standard' in pipeline_raw.strip().lower():
                log.append(f'SKIPPED — Standard pipeline (dropped) — {row_context}')
                skipped += 1
                continue

            existing = Deal.objects.filter(zoho_record_id=zoho_id).first()
            zoho_created = clean_datetime(row.get('Created Time'))
            zoho_modified = clean_datetime(row.get('Modified Time')) or zoho_created
            if edited_since(existing, cutoff):
                log.append(f'KEPT — edited in CRM after last import — {row_context} '
                           f'(changed {existing.updated_at:%Y-%m-%d %H:%M})')
                set_created_at(Deal, existing.pk, zoho_created)
                mark_kept(Deal, existing, cutoff)
                sync_stage_entry(existing, None, zoho_modified)
                kept += 1
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

            old_stage_id = existing.stage_id if existing else None
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
            set_created_at(Deal, obj.pk, zoho_created)
            mark_synced(Deal, obj.pk)
            sync_stage_entry(obj, old_stage_id, zoho_modified)
            created += was_created
            updated += not was_created

        missing = log_missing_from_export(Deal, seen, log)
        summary = (f'Deals — created: {created}, updated: {updated}, kept (edited in CRM): {kept}, '
                   f'skipped: {skipped}, in CRM but not in export: {missing}')
        finish(self, 'import_deals', log, summary, options)
