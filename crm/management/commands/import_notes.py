from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from crm.models import Account, Contact, Deal, Lead, Note
from ._import_utils import resolve_owner, clean_str, clean_datetime, read_export, add_common_arguments, finish

# Zoho's Notes export column names, first match wins. A lookup column is
# exported as a ".id" column plus a display-name column, so the ".id" forms
# come first -- the display name would never match a record.
COLUMN_ALIASES = {
    'id': ['Record Id', 'Note Id', 'Id'],
    'content': ['Note Content', 'Content'],
    'title': ['Note Title', 'Title'],
    'parent': ['Parent ID.id', 'Parent Id.id', 'Related To.id', 'Parent ID', 'Parent Id', 'Related To'],
    'owner': ['Note Owner', 'Created By'],
    'created': ['Created Time'],
}
REQUIRED = ['id', 'content', 'parent']


def pick_columns(df):
    by_lower = {str(c).strip().lower(): c for c in df.columns}
    found = {}
    for key, names in COLUMN_ALIASES.items():
        for name in names:
            if name.lower() in by_lower:
                found[key] = by_lower[name.lower()]
                break
    missing = [k for k in REQUIRED if k not in found]
    if missing:
        raise CommandError(
            f'Could not find the {", ".join(missing)} column(s) in this Notes export. '
            f'Columns in the file: {list(df.columns)}'
        )
    return found


class Command(BaseCommand):
    help = 'Imports Notes from a Zoho export (.xlsx or .csv), attached to their Lead / Deal / Contact / Account'

    def add_arguments(self, parser):
        add_common_arguments(parser, 'Path to Notes_*.xlsx / .csv')

    @transaction.atomic
    def handle(self, *args, **options):
        df = read_export(options['file'])
        cols = pick_columns(df)
        self.stdout.write('Columns used: ' + ', '.join(f'{k}="{v}"' for k, v in cols.items()))

        # Zoho record ids are unique across modules, so one map resolves a
        # note's parent whichever module it belongs to.
        parents = {}
        for model, field in [(Lead, 'lead'), (Contact, 'contact'), (Account, 'account'), (Deal, 'deal')]:
            for pk, zoho_id in model.objects.exclude(zoho_record_id__isnull=True).values_list('pk', 'zoho_record_id'):
                parents[zoho_id] = (field, pk)

        already = set(Note.objects.exclude(zoho_record_id__isnull=True).values_list('zoho_record_id', flat=True))
        log, new_notes, zoho_times, owners = [], [], [], {}
        existing, skipped = 0, 0

        for _, row in df.iterrows():
            zoho_id = clean_str(row.get(cols['id']))
            row_context = f'Note Record Id={zoho_id}'
            if not zoho_id:
                log.append(f'SKIPPED — no Record Id — {row_context}')
                skipped += 1
                continue
            # Notes are only ever added, never overwritten: a note is history,
            # and one already here may have been edited in the CRM since.
            if zoho_id in already:
                existing += 1
                continue

            content = clean_str(row.get(cols['content']))
            title = clean_str(row.get(cols['title'])) if 'title' in cols else ''
            if title and title not in content:
                content = f'{title}\n{content}' if content else title
            if not content:
                log.append(f'SKIPPED — empty note — {row_context}')
                skipped += 1
                continue

            parent_id = clean_str(row.get(cols['parent']))
            target = parents.get(parent_id)
            if target is None:
                log.append(f'UNMATCHED PARENT "{parent_id}" — {row_context}')
                skipped += 1
                continue

            owner_name = clean_str(row.get(cols['owner'])) if 'owner' in cols else ''
            if owner_name not in owners:
                owners[owner_name] = resolve_owner(owner_name, log, row_context)

            field, pk = target
            new_notes.append(Note(
                content=content, created_by=owners[owner_name], zoho_record_id=zoho_id, **{f'{field}_id': pk},
            ))
            zoho_times.append(clean_datetime(row.get(cols['created'])) if 'created' in cols else None)
            already.add(zoho_id)

        Note.objects.bulk_create(new_notes, batch_size=500)
        # auto_now_add stamped every note with today; give back Zoho's times.
        dated = []
        for note, when in zip(new_notes, zoho_times):
            if when is not None:
                note.created_at = when
                dated.append(note)
        Note.objects.bulk_update(dated, ['created_at'], batch_size=500)

        by_parent = {}
        for note in new_notes:
            for field in ('lead', 'contact', 'account', 'deal'):
                if getattr(note, f'{field}_id'):
                    by_parent[field] = by_parent.get(field, 0) + 1
        summary = (f'Notes — created: {len(new_notes)} '
                   f'({", ".join(f"{n} on {f}s" for f, n in sorted(by_parent.items())) or "none"}), '
                   f'already imported: {existing}, skipped: {skipped}')
        finish(self, 'import_notes', log, summary, options)
