import glob
import os
from collections import Counter

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ._import_utils import read_export, resolve_owner

# Order matters: each step links to records the earlier ones created.
STEPS = [
    ('import_accounts', 'Accounts', 'Account Owner', True),
    ('import_contacts', 'Contacts', 'Contact Owner', True),
    ('import_deals', 'Deals', 'Deal Owner', True),
    ('import_leads', 'Leads', 'Lead Owner', True),
    ('import_notes', 'Notes', None, False),
]


def newest_export(folder, prefix):
    matches = []
    for ext in ('xlsx', 'csv'):
        matches += glob.glob(os.path.join(folder, f'{prefix}_*.{ext}'))
        matches += glob.glob(os.path.join(folder, f'{prefix}.{ext}'))
    return max(matches, key=os.path.getmtime) if matches else None


class Command(BaseCommand):
    help = ('Cut-over import from a folder of Zoho exports: Accounts, Contacts, Deals, Leads, then Notes, '
            'in order and as one transaction -- a failure anywhere saves nothing.')

    def add_arguments(self, parser):
        parser.add_argument('--dir', required=True, help='Folder holding the Zoho exports (Accounts_*.xlsx, ...)')
        parser.add_argument('--dry-run', action='store_true',
                            help='Run all five steps and report, then roll the whole import back.')
        parser.add_argument('--edited-after', default=None,
                            help='Records changed in the CRM after this time ("YYYY-MM-DD HH:MM") are left as '
                                 'they are. Defaults to each step\'s last import logged on this server.')

    def handle(self, *args, **options):
        folder = options['dir']
        if not os.path.isdir(folder):
            raise CommandError(f'No such folder: {folder}')

        plan = []
        for command, prefix, owner_column, required in STEPS:
            path = newest_export(folder, prefix)
            if path is None:
                if required:
                    raise CommandError(f'No {prefix}_*.xlsx or {prefix}_*.csv in {folder}')
                self.stdout.write(self.style.WARNING(f'No {prefix} export in {folder} -- that step is skipped.'))
                continue
            plan.append((command, prefix, owner_column, path))

        self.stdout.write(self.style.MIGRATE_HEADING('Files'))
        for _, prefix, _, path in plan:
            self.stdout.write(f'  {prefix:9s} {path}')
        self.check_owners(plan)

        with transaction.atomic():
            for command, prefix, _, path in plan:
                self.stdout.write(self.style.MIGRATE_HEADING(f'\n{prefix}'))
                call_command(
                    command, file=path, dry_run=options['dry_run'],
                    edited_after=options['edited_after'], wrapped=True,
                )
            if options['dry_run']:
                transaction.set_rollback(True)

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('\nDRY RUN -- all of the above was rolled back. Nothing was saved.'))
        else:
            self.stdout.write(self.style.SUCCESS('\nImport committed.'))

    def check_owners(self, plan):
        """Records whose Zoho owner has no CRM user are skipped, so show the
        mapping before anything runs -- users missing on cut-over day are the
        likeliest way to lose records."""
        names = Counter()
        for _, _, owner_column, path in plan:
            if not owner_column:
                continue
            df = read_export(path)
            if owner_column in df.columns:
                names.update(df[owner_column].dropna().astype(str).str.strip())

        self.stdout.write(self.style.MIGRATE_HEADING('\nZoho owner -> CRM user'))
        unmatched = []
        for name, count in names.most_common():
            user = resolve_owner(name, [], '')
            self.stdout.write(f'  {name:30s} -> {user.username if user else "NO USER":15s} {count:6d} records')
            if user is None:
                unmatched.append(name)
        if unmatched:
            self.stdout.write(self.style.ERROR(
                f'  {len(unmatched)} owner(s) have no CRM user; their records will be SKIPPED: '
                f'{", ".join(unmatched)}. Create those users (username or first name matching) first.'
            ))
