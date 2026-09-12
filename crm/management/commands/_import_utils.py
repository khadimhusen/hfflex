import argparse
import glob
import os
import re
from collections import Counter
from datetime import datetime, timedelta

import pandas as pd
from django.contrib.auth.models import User
from django.core.management.base import CommandError
from django.db import transaction
from django.db.models import F

LOG_DIR = os.path.join('crm', 'import_logs')


def resolve_owner(owner_name, log, row_context):
    """Best-effort match a Zoho owner name to a Django User. Falls back to
    None if no match — caller decides whether that's fatal for this model."""
    if not owner_name or str(owner_name).strip() == '' or str(owner_name) == 'nan':
        return None

    owner_name = str(owner_name).strip()
    user = (
            User.objects.filter(username__iexact=owner_name).first()
            or User.objects.filter(first_name__iexact=owner_name).first()
            or User.objects.filter(email__iexact=owner_name).first()
    )
    if user is None:
        log.append(f'UNMATCHED OWNER "{owner_name}" — {row_context}')
    return user


def clean_str(value, max_length=None):
    """Excel blanks come through as NaN (a float), not '' — normalize those to ''."""
    if value is None or str(value) == 'nan':
        return ''
    value = str(value).strip()
    return value[:max_length] if max_length else value


def clean_decimal(value):
    if value is None or str(value) == 'nan':
        return None
    return value


def clean_datetime(value):
    if value is None or str(value) == 'nan' or str(value).strip() == '':
        return None
    parsed = pd.to_datetime(value, errors='coerce')
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def clean_bool(value):
    # A CSV export gives "true"/"false" text, and bool("false") is True.
    if value is None or str(value) == 'nan':
        return False
    if isinstance(value, str):
        return value.strip().lower() in ('true', '1', 'yes')
    return bool(value)


def read_export(path):
    """Zoho exports as .xlsx or .csv. CSV is read as text throughout so ids
    and codes can't be turned into floats; clean_* and Django's own field
    conversion take care of the rest."""
    if str(path).lower().endswith('.csv'):
        return pd.read_csv(path, dtype=str, encoding='utf-8-sig')
    return pd.read_excel(path)


def add_common_arguments(parser, file_help):
    parser.add_argument('--file', type=str, required=True, help=file_help)
    parser.add_argument('--dry-run', action='store_true',
                        help='Run the whole import and report what would change, then roll everything back.')
    parser.add_argument('--edited-after', type=str, default=None,
                        help='For records imported before sync times were kept: ones changed in the CRM after '
                             'this time ("YYYY-MM-DD HH:MM") are left as they are. Defaults to the time of the '
                             'last import logged on this server.')
    # Set by import_zoho, which owns the transaction (and the dry-run
    # rollback) for all five steps.
    parser.add_argument('--wrapped', action='store_true', help=argparse.SUPPRESS)


def write_log_file(command_name, log_lines, summary_line, dry_run=False):
    """Writes the import log to a timestamped file under crm/import_logs/.

    A real run's file name doubles as the record of when this database last
    took an import (see latest_import_time), so dry runs get their own suffix
    and are never mistaken for one."""
    os.makedirs(LOG_DIR, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    suffix = '_DRYRUN' if dry_run else ''
    log_path = os.path.join(LOG_DIR, f'{command_name}_{timestamp}{suffix}.log')

    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(f'{summary_line}\n')
        f.write(f'Run at: {datetime.now().isoformat()}\n')
        f.write('=' * 60 + '\n\n')
        if log_lines:
            for line in log_lines:
                f.write(line + '\n')
        else:
            f.write('No issues.\n')

    return log_path


def latest_import_time(command_name):
    """When the last real import finished, to the microsecond.

    The log is written after the import's last save, and its "Run at:" line
    has full precision. The file name only has whole seconds, and every row
    saved in that final second is *later* than the truncated time -- which
    made hundreds of freshly imported rows look edited in the CRM."""
    files = [
        f for f in glob.glob(os.path.join(LOG_DIR, f'{command_name}_*.log'))
        if not f.endswith('_DRYRUN.log')
    ]
    if not files:
        return None
    newest = max(files)
    with open(newest, encoding='utf-8') as f:
        for line in f.readlines()[:3]:
            if line.startswith('Run at:'):
                try:
                    return datetime.fromisoformat(line.split(':', 1)[1].strip())
                except ValueError:
                    break
    stamp = os.path.basename(newest)[len(command_name) + 1:len(command_name) + 16]
    return datetime.strptime(stamp, '%Y%m%d_%H%M%S') + timedelta(seconds=1)


# ---- "keep our edits" -----------------------------------------------------
#
# Every record the import writes gets zoho_synced_at = its updated_at. Any
# later save moves updated_at past that, which is how a CRM edit is spotted:
# the import then leaves the record alone (KEPT), on this run and every run
# after. Records imported before zoho_synced_at existed have it empty; for
# those, the time of the last logged import (or --edited-after) stands in.

def resolve_edit_cutoff(command_name, model, edited_after):
    """The stand-in sync time for records imported before zoho_synced_at
    existed. Returns (cutoff, where-it-came-from)."""
    legacy = (
        model.objects.filter(zoho_synced_at__isnull=True)
        .exclude(zoho_record_id__isnull=True).exclude(zoho_record_id='')
    )
    if not legacy.exists():
        return None, 'every imported record carries its own sync time'

    if edited_after:
        parsed = pd.to_datetime(edited_after, errors='coerce')
        if pd.isna(parsed):
            raise CommandError(f'--edited-after: cannot read "{edited_after}" as a date/time.')
        return parsed.to_pydatetime(), 'from --edited-after'

    logged = latest_import_time(command_name)
    if logged:
        return logged, f'last {command_name} run logged on this server'

    raise CommandError(
        f'This database already holds imported {model.__name__} records, but there is no '
        f'{command_name} log saying when they were imported — so edits made in the CRM since '
        f'cannot be told apart from imported data. Re-run with '
        f'--edited-after "YYYY-MM-DD HH:MM" set to the time of that import.'
    )


def edited_since(obj, cutoff):
    """True if someone changed this record in the CRM since the import last wrote it."""
    if obj is None or obj.updated_at is None:
        return False
    baseline = obj.zoho_synced_at or cutoff
    return baseline is not None and obj.updated_at > baseline


def mark_synced(model, pk):
    # Exactly equal to updated_at, so the very next save counts as an edit.
    model.objects.filter(pk=pk).update(zoho_synced_at=F('updated_at'))


def mark_kept(model, obj, cutoff):
    # Pin a kept record's sync time to the import it was last in step with,
    # so it stays protected on later runs too -- not just until the next
    # import's log moves the stand-in cutoff forward.
    if obj.zoho_synced_at is None and cutoff is not None:
        model.objects.filter(pk=obj.pk).update(zoho_synced_at=cutoff)


def set_created_at(model, pk, value):
    # created_at is auto_now_add, so save() always stamps it with "now".
    # A queryset update writes Zoho's own creation time without touching
    # updated_at (auto_now only fires on save()).
    if value is not None:
        model.objects.filter(pk=pk).update(created_at=value)


def log_missing_from_export(model, seen_ids, log):
    """Imported records that are no longer in the export — deleted, merged or
    filtered out in Zoho. Reported only; never deleted here."""
    missing = list(
        model.objects.exclude(zoho_record_id__isnull=True).exclude(zoho_record_id='')
        .exclude(zoho_record_id__in=set(seen_ids))
        .values_list('pk', 'zoho_record_id')
    )
    for pk, zoho_id in missing:
        log.append(f'NOT IN EXPORT — {model.__name__} #{pk} (Zoho {zoho_id})')
    return len(missing)


def finish(command, command_name, log, summary, options):
    if options['dry_run']:
        summary = f'DRY RUN, nothing saved — {summary}'

    # Tally log lines by kind: with thousands of rows, one line per record on
    # screen buries the problems. The full list goes in the log file.
    sep = ' — '
    kinds = Counter(re.sub(r'"[^"]*"', '"..."', sep.join(line.split(sep)[:-1]) or line) for line in log)
    for kind, n in kinds.most_common():
        command.stdout.write(f'  {n:6d}  {kind}')

    # People edit records one at a time; hundreds "edited" in the same
    # second is a bulk update, and those records probably should not be kept.
    kept_at = Counter()
    for line in log:
        if line.startswith('KEPT'):
            match = re.search(r'\(changed ([0-9: -]+)\)$', line)
            if match:
                kept_at[match.group(1)] += 1
    if kept_at:
        command.stdout.write('  kept records by when they were changed in the CRM (busiest minutes):')
        for when, n in kept_at.most_common(5):
            command.stdout.write(f'      {when}  {n:6d}')

    command.stdout.write(command.style.SUCCESS(summary))

    if options['dry_run']:
        command.stdout.write(f'  Log: {write_log_file(command_name, log, summary, dry_run=True)}')
        if not options['wrapped']:
            transaction.set_rollback(True)
    else:
        # Written only once the import has committed: the file's timestamp is
        # what the next run treats as "last import", so a run that fails and
        # rolls back must not leave one behind.
        transaction.on_commit(
            lambda: command.stdout.write(f'  Log: {write_log_file(command_name, log, summary)}')
        )
