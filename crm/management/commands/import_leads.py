from django.core.management.base import BaseCommand
from django.db import transaction
from crm.models import Account, Contact, Deal, Lead
from ._import_utils import (
    resolve_owner, clean_str, clean_decimal, clean_datetime, clean_bool, read_export, add_common_arguments,
    resolve_edit_cutoff, edited_since, set_created_at, mark_synced, mark_kept, log_missing_from_export, finish,
)


class Command(BaseCommand):
    help = 'Imports Leads from a Zoho export (.xlsx or .csv)'

    def add_arguments(self, parser):
        add_common_arguments(parser, 'Path to Leads_*.xlsx / .csv')

    @transaction.atomic
    def handle(self, *args, **options):
        df = read_export(options['file'])
        cutoff, cutoff_source = resolve_edit_cutoff('import_leads', Lead, options['edited_after'])
        self.stdout.write(f'Keeping CRM edits made after: {cutoff or "n/a"} ({cutoff_source})')
        log, seen = [], []
        created, updated, kept, skipped = 0, 0, 0, 0

        for _, row in df.iterrows():
            zoho_id = clean_str(row.get('Record Id'))
            last_name = clean_str(row.get('Last Name'))
            row_context = f'Lead Record Id={zoho_id}, {last_name}'

            if not zoho_id:
                log.append(f'SKIPPED — no Record Id — {row_context}')
                skipped += 1
                continue
            seen.append(zoho_id)

            if not last_name:
                log.append(f'SKIPPED — no Last Name — {row_context}')
                skipped += 1
                continue

            existing = Lead.objects.filter(zoho_record_id=zoho_id).first()
            zoho_created = clean_datetime(row.get('Created Time'))
            if edited_since(existing, cutoff):
                log.append(f'KEPT — edited in CRM after last import — {row_context} '
                           f'(changed {existing.updated_at:%Y-%m-%d %H:%M})')
                set_created_at(Lead, existing.pk, zoho_created)
                mark_kept(Lead, existing, cutoff)
                kept += 1
                continue

            owner = resolve_owner(row.get('Lead Owner'), log, row_context)
            if owner is None:
                log.append(f'SKIPPED — no matching owner — {row_context}')
                skipped += 1
                continue

            # Resolve conversion links — a Lead may reference an Account/Contact/Deal
            # that was itself skipped during its own import (unmatched owner, etc.),
            # so treat these as best-effort, not fatal.
            converted_account = None
            acc_zoho_id = clean_str(row.get('Converted Account.id'))
            if acc_zoho_id:
                converted_account = Account.objects.filter(zoho_record_id=acc_zoho_id).first()
                if converted_account is None:
                    log.append(f'UNMATCHED converted Account "{acc_zoho_id}" — {row_context}')

            converted_contact = None
            con_zoho_id = clean_str(row.get('Converted Contact.id'))
            if con_zoho_id:
                converted_contact = Contact.objects.filter(zoho_record_id=con_zoho_id).first()
                if converted_contact is None:
                    log.append(f'UNMATCHED converted Contact "{con_zoho_id}" — {row_context}')

            converted_deal = None
            deal_zoho_id = clean_str(row.get('Converted Deal.id'))
            if deal_zoho_id:
                converted_deal = Deal.objects.filter(zoho_record_id=deal_zoho_id).first()
                if converted_deal is None:
                    log.append(f'UNMATCHED converted Deal "{deal_zoho_id}" — {row_context}')

            obj, was_created = Lead.objects.update_or_create(
                zoho_record_id=zoho_id,
                defaults={
                    'first_name': clean_str(row.get('First Name'), 100),
                    'last_name': last_name,
                    'company': clean_str(row.get('Company'), 255),
                    'title': clean_str(row.get('Title'), 100),
                    'email': clean_str(row.get('Email'), 254),
                    'phone': clean_str(row.get('Phone'), 30),
                    'mobile': clean_str(row.get('Mobile'), 30),
                    'street': clean_str(row.get('Street'), 255),
                    'city': clean_str(row.get('City'), 100),
                    'state': clean_str(row.get('State'), 100),
                    'country': clean_str(row.get('Country'), 100),
                    'zip_code': clean_str(row.get('Zip Code'), 20),
                    'lead_source': clean_str(row.get('Lead Source'), 50),
                    'lead_status': clean_str(row.get('Lead Status'), 50),
                    'industry': clean_str(row.get('Industry'), 100),
                    'annual_revenue': clean_decimal(row.get('Annual Revenue')),
                    'description': clean_str(row.get('Description')),
                    'im_query_type': clean_str(row.get('IM_QUERY TYPE'), 100),
                    'im_query_id': clean_str(row.get('IM_QUERY ID'), 100),
                    'im_enquiry_time': clean_datetime(row.get('IM_ENQUIRY TIME')),
                    'im_product': clean_str(row.get('IM_PRODUCT'), 255),
                    'is_converted': clean_bool(row.get('Is Converted')),
                    'converted_account': converted_account,
                    'converted_contact': converted_contact,
                    'converted_deal': converted_deal,
                    'converted_at': clean_datetime(row.get('Converted Date Time')),
                    'owner': owner,
                },
            )
            set_created_at(Lead, obj.pk, zoho_created)
            mark_synced(Lead, obj.pk)
            created += was_created
            updated += not was_created

        missing = log_missing_from_export(Lead, seen, log)
        summary = (f'Leads — created: {created}, updated: {updated}, kept (edited in CRM): {kept}, '
                   f'skipped: {skipped}, in CRM but not in export: {missing}')
        finish(self, 'import_leads', log, summary, options)
