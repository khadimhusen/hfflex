import io
import os
import zipfile
from collections import Counter
from datetime import datetime

import pandas as pd
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from crm.models import Account, Contact, Deal, DealAttachment, Lead, Note
from ._import_utils import LOG_DIR, clean_datetime, clean_str, resolve_owner, write_log_file

PARENT_MODELS = [(Deal, 'deal'), (Lead, 'lead'), (Contact, 'contact'), (Account, 'account')]
PARENT_FIELDS = ('lead', 'contact', 'account', 'deal')


def read_module(zf, module):
    """Every part of one module's CSV in a Zoho data backup (Notes_001.csv,
    Notes_002.csv, ...) as one DataFrame of text."""
    names = sorted(
        n for n in zf.namelist()
        if n.startswith('Data/') and os.path.basename(n).startswith(f'{module}_') and n.lower().endswith('.csv')
    )
    if not names:
        raise CommandError(f'No Data/{module}_*.csv in {zf.filename}')
    return pd.concat(
        [pd.read_csv(io.BytesIO(zf.read(n)), dtype=str, encoding='utf-8-sig') for n in names],
        ignore_index=True,
    )


class Command(BaseCommand):
    help = ('Notes and deal attachments from a Zoho CRM data backup (Data_*.zip, plus Attachments_*.zip for '
            'the files). Places notes by Parent ID, moves already-imported notes that sit on the wrong '
            'record, and copies deal attachment files into media. Safe to re-run.')

    def add_arguments(self, parser):
        parser.add_argument('--data', required=True, help='Zoho backup Data_*.zip')
        parser.add_argument('--attachments', nargs='*', default=[],
                            help='Zoho backup Attachments_*.zip file(s); omit to do notes only')
        parser.add_argument('--dry-run', action='store_true',
                            help='Report what would happen and save nothing -- no rows, no files.')

    def handle(self, *args, **options):
        dry = options['dry_run']
        data = zipfile.ZipFile(options['data'])
        users = read_module(data, 'Users')
        notes = read_module(data, 'Notes')
        atts = read_module(data, 'Attachments') if options['attachments'] else None
        log = []

        # The backup names people by Zoho user id; its Users file gives the
        # name, and resolve_owner (zoho_owner_map.json, then name matching)
        # turns that name into our user.
        self.users = {}
        for r in users.to_dict('records'):
            name = ' '.join(x for x in (clean_str(r.get('First Name')), clean_str(r.get('Last Name'))) if x)
            self.users[clean_str(r.get('Record Id'))] = resolve_owner(name, log, f'Zoho user {name}') if name else None

        self.parents = {}
        for model, field in PARENT_MODELS:
            for pk, zoho_id in model.objects.exclude(zoho_record_id__isnull=True).values_list('pk', 'zoho_record_id'):
                self.parents[zoho_id] = (field, pk)

        with transaction.atomic():
            note_summary = self.import_notes(notes, log)
            if dry:
                transaction.set_rollback(True)

        att_summary, review = 'Attachments — skipped (no --attachments zip given)', []
        if atts is not None:
            att_summary, review = self.import_attachments(atts, notes, options['attachments'], log, dry)

        prefix = 'DRY RUN, nothing saved — ' if dry else ''
        sep = ' — '
        for kind, n in Counter(sep.join(line.split(sep)[:-1]) or line for line in log).most_common():
            self.stdout.write(f'  {n:6d}  {kind}')
        self.stdout.write(self.style.SUCCESS(prefix + note_summary))
        self.stdout.write(self.style.SUCCESS(prefix + att_summary))
        if review:
            os.makedirs(LOG_DIR, exist_ok=True)
            path = os.path.join(
                LOG_DIR,
                f'import_zoho_backup_{datetime.now():%Y%m%d_%H%M%S}_attachments_not_imported'
                f'{"_DRYRUN" if dry else ""}.xlsx',
            )
            pd.DataFrame(review).to_excel(path, index=False)
            self.stdout.write(f'  {len(review)} attachments not imported, listed for review in: {path}')
        summary = f'{prefix}{note_summary} | {att_summary}'
        self.stdout.write(f'  Log: {write_log_file("import_zoho_backup", log, summary, dry_run=dry)}')

    # ---- notes -------------------------------------------------------------

    def import_notes(self, notes, log):
        existing = {n.zoho_record_id: n for n in Note.objects.exclude(zoho_record_id__isnull=True)}
        new_notes, zoho_times, seen = [], [], set()
        moved = in_place = skipped = 0

        for r in notes.to_dict('records'):
            zoho_id = clean_str(r.get('Record Id'))
            ctx = f'Note {zoho_id}'
            if not zoho_id or zoho_id in seen:
                continue
            seen.add(zoho_id)
            status = clean_str(r.get('Record Status'))
            if status and status != 'Available':
                log.append(f'SKIPPED — note not Available in Zoho ({status}) — {ctx}')
                skipped += 1
                continue

            module = clean_str(r.get('Parent Id.Module'))
            target = self.parents.get(clean_str(r.get('Parent.id')))

            note = existing.get(zoho_id)
            if note is not None:
                # Already imported (the deal-notes report placed them by deal
                # name, and a shared name can pick the wrong deal): put it on
                # the record Zoho says it belongs to.
                if target is None:
                    in_place += 1
                    continue
                field, pk = target
                current = {f: getattr(note, f'{f}_id') for f in PARENT_FIELDS}
                if current[field] == pk and sum(1 for v in current.values() if v) == 1:
                    in_place += 1
                    continue
                was = ', '.join(f'{f} #{v}' for f, v in current.items() if v) or 'nothing'
                values = {f'{f}_id': None for f in PARENT_FIELDS}
                values[f'{field}_id'] = pk
                Note.objects.filter(pk=note.pk).update(**values)
                log.append(f'MOVED — note was on the wrong record — {ctx}: {was} -> {field} #{pk}')
                moved += 1
                continue

            if target is None:
                log.append(f'NOT PLACED — parent is a Zoho {module or "?"} record not in the CRM — {ctx}')
                skipped += 1
                continue

            content = clean_str(r.get('Note Content'))
            title = clean_str(r.get('Note Title'))
            if title and title not in content:
                content = f'{title}\n{content}' if content else title
            if not content:
                log.append(f'SKIPPED — empty note — {ctx}')
                skipped += 1
                continue

            field, pk = target
            new_notes.append(Note(
                content=content, created_by=self.users.get(clean_str(r.get('Note Owner.id'))),
                zoho_record_id=zoho_id, **{f'{field}_id': pk},
            ))
            zoho_times.append(clean_datetime(r.get('Created Time')))

        Note.objects.bulk_create(new_notes, batch_size=500)
        # auto_now_add stamped every note with today; give back Zoho's times.
        dated = []
        for note, when in zip(new_notes, zoho_times):
            if when is not None:
                note.created_at = when
                dated.append(note)
        Note.objects.bulk_update(dated, ['created_at'], batch_size=500)

        by_parent = Counter(next(f for f in PARENT_FIELDS if getattr(n, f'{f}_id')) for n in new_notes)
        placed = ', '.join(f'{n} on {f}s' for f, n in sorted(by_parent.items())) or 'none'
        return (f'Notes — created: {len(new_notes)} ({placed}), moved to the right record: {moved}, '
                f'already in place: {in_place}, skipped / not placed: {skipped}')

    # ---- attachments ---------------------------------------------------------

    def import_attachments(self, atts, notes, zip_paths, log, dry):
        files = {}
        for path in zip_paths:
            zf = zipfile.ZipFile(path)
            for info in zf.infolist():
                if not info.is_dir():
                    files[os.path.basename(info.filename)] = (zf, info)

        # A file attached to a Zoho note belongs on that note's record.
        note_parent = {clean_str(r.get('Record Id')): clean_str(r.get('Parent.id')) for r in notes.to_dict('records')}
        deals = {zoho_id: pk for zoho_id, (field, pk) in self.parents.items() if field == 'deal'}
        done = set(DealAttachment.objects.exclude(zoho_record_id__isnull=True).values_list('zoho_record_id', flat=True))
        imported = already = total_bytes = 0
        review = []

        for r in atts.to_dict('records'):
            zoho_id = clean_str(r.get('Old Attachment Id')) or clean_str(r.get('Record Id'))
            file_key = clean_str(r.get('Record Id'))
            name = clean_str(r.get('File Name')) or file_key
            ctx = f'Attachment {zoho_id} ({name})'
            if zoho_id in done:
                already += 1
                continue
            status = clean_str(r.get('Record Status'))
            if status and status != 'Available':
                log.append(f'SKIPPED — attachment not Available in Zoho ({status}) — {ctx}')
                continue

            module = clean_str(r.get('Parent Id.Module'))
            parent, via = clean_str(r.get('Parent.id')), ''
            if module == 'Notes':
                parent, via = note_parent.get(parent, ''), ' (via its note)'
            deal_pk = deals.get(parent)

            reason = None
            if deal_pk is None:
                where = self.parents.get(parent, (None,))[0]
                reason = (f'attached{via} to a {where} -- only deals take attachments' if where
                          else f'attached{via} to a Zoho {module or "?"} record not in the CRM')
            elif file_key not in files:
                reason = 'file missing from the attachments zip'
            if reason:
                review.append({
                    'File Name': name, 'Reason': reason, 'Zoho module': module,
                    'Zoho parent id': clean_str(r.get('Parent.id')), 'Created Time': clean_str(r.get('Created Time')),
                })
                log.append(f'NOT IMPORTED — {reason} — {ctx}')
                continue

            zf, info = files[file_key]
            if not dry:
                att = DealAttachment(
                    deal_id=deal_pk, original_filename=name[:255], zoho_record_id=zoho_id,
                    uploaded_by=self.users.get(clean_str(r.get('Attachment Owner.id'))),
                )
                try:
                    with transaction.atomic():
                        att.file.save(name, ContentFile(zf.read(info)), save=False)
                        att.save()
                        when = clean_datetime(r.get('Created Time'))
                        if when is not None:
                            DealAttachment.objects.filter(pk=att.pk).update(uploaded_at=when)
                except Exception as exc:
                    # No row means no file: don't leave an orphan in media.
                    if att.file.name:
                        att.file.storage.delete(att.file.name)
                    review.append({'File Name': name, 'Reason': f'failed to save: {exc}', 'Zoho module': module,
                                   'Zoho parent id': clean_str(r.get('Parent.id')),
                                   'Created Time': clean_str(r.get('Created Time'))})
                    log.append(f'FAILED — could not save the file — {ctx}: {exc}')
                    continue
            imported += 1
            total_bytes += info.file_size
            done.add(zoho_id)

        verb = 'would import' if dry else 'imported'
        return (f'Attachments — {verb}: {imported} files ({total_bytes / 1e6:.0f} MB) onto deals, '
                f'already imported: {already}, not imported (listed for review): {len(review)}'), review
