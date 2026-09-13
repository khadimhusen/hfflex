import os
from collections import Counter, defaultdict
from datetime import datetime

import pandas as pd
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from crm.models import Account, Contact, Deal, Lead, Note
from ._import_utils import (
    LOG_DIR, resolve_owner, clean_str, clean_datetime, read_export, add_common_arguments, finish,
)

# Zoho's Notes export column names, first match wins. A lookup column is
# exported as a ".id" column plus a display-name column, so the ".id" forms
# come first -- the display name would never match a record.
COLUMN_ALIASES = {
    'id': ['Record Id', 'Note Id', 'Id'],
    'content': ['Note Content', 'Content'],
    'title': ['Note Title', 'Title'],
    'parent': ['Parent ID.id', 'Parent Id.id', 'Related To.id', 'Parent ID', 'Parent Id', 'Related To'],
    # A Zoho *report* of deal notes has no parent id, only the deal's name.
    'deal_name': ['Deal Name'],
    'owner': ['Note Owner', 'Created By'],
    'created': ['Created Time'],
}


def pick_columns(df):
    by_lower = {str(c).strip().lower(): c for c in df.columns}
    found = {}
    for key, names in COLUMN_ALIASES.items():
        for name in names:
            if name.lower() in by_lower:
                found[key] = by_lower[name.lower()]
                break
    missing = [k for k in ('id', 'content') if k not in found]
    if 'parent' not in found and 'deal_name' not in found:
        missing.append('parent (Parent ID, or Deal Name in a deal-notes report)')
    if missing:
        raise CommandError(
            f'Could not find the {", ".join(missing)} column(s) in this Notes export. '
            f'Columns in the file: {list(df.columns)}'
        )
    return found


class DealNameMatcher:
    """Places a note on a deal when all the export gives is the deal's name.

    Names repeat ("rahul", "deepak industries"), so a name decides alone only
    when exactly one imported deal has it. Otherwise the note's author must
    own the deal and the deal must be older than the note -- on the notes
    whose deal is certain, those hold 93.5% and 95.9% of the time. A note
    still left with several candidates is not guessed at; it goes to the
    review file. Only Zoho-imported deals are candidates: a Zoho note cannot
    belong to a deal created in this CRM.
    """

    def __init__(self):
        self.by_name = defaultdict(list)
        deals = Deal.objects.exclude(zoho_record_id__isnull=True).values_list('pk', 'name', 'owner_id', 'created_at')
        for pk, name, owner_id, created in deals:
            self.by_name[name.strip().lower()].append((pk, owner_id, created))
        self.usernames = dict(User.objects.values_list('id', 'username'))

    def match(self, deal_name, author, when):
        """Returns (deal pk or None, how it was decided, candidates)."""
        if not deal_name:
            return None, 'no deal name', []
        candidates = self.by_name.get(deal_name.strip().lower(), [])
        if not candidates:
            return None, 'no imported deal with this name', []
        if len(candidates) == 1:
            return candidates[0][0], 'unique deal name', candidates

        author_id = author.id if author else None
        by_owner = [c for c in candidates if c[1] == author_id]
        by_both = [c for c in by_owner if when is not None and c[2] <= when]
        if len(by_both) == 1:
            return by_both[0][0], 'name + author owns it + deal older', candidates
        if len(by_owner) == 1:
            return by_owner[0][0], 'name + author owns it', candidates
        by_time = [c for c in candidates if when is not None and c[2] <= when]
        if not by_owner and len(by_time) == 1:
            return by_time[0][0], 'name + only deal older than note', candidates
        return None, 'several deals with this name', candidates

    def describe(self, candidates):
        return ', '.join(
            f'#{pk} ({self.usernames.get(owner_id, "?")}, {created:%Y-%m-%d})' for pk, owner_id, created in candidates
        )


class Command(BaseCommand):
    help = ('Imports Notes from a Zoho export (.xlsx or .csv), attached to their Lead / Deal / Contact / Account '
            'by Parent ID -- or, for a deal-notes report with only a Deal Name, to the deal that name identifies')

    def add_arguments(self, parser):
        add_common_arguments(parser, 'Path to Notes_*.xlsx / .csv, or a deal-notes report')

    @transaction.atomic
    def handle(self, *args, **options):
        df = read_export(options['file'])
        cols = pick_columns(df)
        by_name = 'parent' not in cols
        self.stdout.write('Columns used: ' + ', '.join(f'{k}="{v}"' for k, v in cols.items()))

        if by_name:
            self.stdout.write('No Parent ID column: attaching notes to deals by Deal Name.')
            matcher = DealNameMatcher()
        else:
            # Zoho record ids are unique across modules, so one map resolves a
            # note's parent whichever module it belongs to.
            parents = {}
            for model, field in [(Lead, 'lead'), (Contact, 'contact'), (Account, 'account'), (Deal, 'deal')]:
                for pk, zoho_id in model.objects.exclude(zoho_record_id__isnull=True).values_list('pk', 'zoho_record_id'):
                    parents[zoho_id] = (field, pk)

        already = set(Note.objects.exclude(zoho_record_id__isnull=True).values_list('zoho_record_id', flat=True))
        log, new_notes, zoho_times, owners, unplaced = [], [], [], {}, []
        placed_how = Counter()
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

            owner_name = clean_str(row.get(cols['owner'])) if 'owner' in cols else ''
            if owner_name not in owners:
                owners[owner_name] = resolve_owner(owner_name, log, row_context)
            when = clean_datetime(row.get(cols['created'])) if 'created' in cols else None

            if by_name:
                deal_pk, how, candidates = matcher.match(clean_str(row.get(cols['deal_name'])), owners[owner_name], when)
                if deal_pk is None:
                    log.append(f'NOT PLACED — {how} — {row_context}')
                    unplaced.append({**{c: row.get(c) for c in df.columns},
                                     'Reason not imported': how,
                                     'Candidate deals (#id, owner, created)': matcher.describe(candidates)})
                    continue
                placed_how[how] += 1
                field, pk = 'deal', deal_pk
            else:
                parent_id = clean_str(row.get(cols['parent']))
                target = parents.get(parent_id)
                if target is None:
                    log.append(f'UNMATCHED PARENT "{parent_id}" — {row_context}')
                    skipped += 1
                    continue
                field, pk = target
                placed_how[f'on {field}s'] += 1

            new_notes.append(Note(
                content=content, created_by=owners[owner_name], zoho_record_id=zoho_id, **{f'{field}_id': pk},
            ))
            zoho_times.append(when)
            already.add(zoho_id)

        Note.objects.bulk_create(new_notes, batch_size=500)
        # auto_now_add stamped every note with today; give back Zoho's times.
        dated = []
        for note, when in zip(new_notes, zoho_times):
            if when is not None:
                note.created_at = when
                dated.append(note)
        Note.objects.bulk_update(dated, ['created_at'], batch_size=500)

        if unplaced:
            os.makedirs(LOG_DIR, exist_ok=True)
            suffix = '_DRYRUN' if options['dry_run'] else ''
            review_path = os.path.join(
                LOG_DIR, f'import_notes_{datetime.now():%Y%m%d_%H%M%S}_not_imported{suffix}.xlsx')
            pd.DataFrame(unplaced).to_excel(review_path, index=False)
            self.stdout.write(f'  {len(unplaced)} notes not imported, listed for review in: {review_path}')

        placement = ', '.join(f'{n} {how}' for how, n in placed_how.most_common()) or 'none'
        summary = (f'Notes — created: {len(new_notes)} ({placement}), not imported (for review): {len(unplaced)}, '
                   f'already imported: {existing}, skipped: {skipped}')
        finish(self, 'import_notes', log, summary, options)
