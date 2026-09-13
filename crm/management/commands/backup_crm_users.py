import os
from datetime import datetime

import pandas as pd
from django.contrib.auth.models import User
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from crm.models import Account, Contact, Deal, Lead, Note, DealTask, DealStageHistory, DealAttachment


def find_user(token):
    """A username, or a name like "chandrakant kamble" (every word must match
    the username, first or last name). Refuses to guess between two people."""
    token = token.strip()
    exact = list(User.objects.filter(username__iexact=token))
    if len(exact) == 1:
        return exact[0]

    q = Q()
    for word in token.split():
        q &= Q(username__icontains=word) | Q(first_name__icontains=word) | Q(last_name__icontains=word)
    matches = list(User.objects.filter(q))
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise CommandError(f'No user matches "{token}".')
    raise CommandError(
        f'"{token}" matches {len(matches)} users: '
        + '; '.join(f'{u.username} ({u.get_full_name() or "-"}, {"active" if u.is_active else "inactive"})'
                    for u in matches)
        + '. Use the username, or first and last name together.'
    )


class Command(BaseCommand):
    help = ('Read-only backup of the CRM records the given users own or have worked on: an .xlsx to read '
            'and a .json that `manage.py loaddata` can restore from.')

    def add_arguments(self, parser):
        parser.add_argument('--users', nargs='+', required=True,
                            help='Usernames or names, e.g. --users chandrakant "kapil bhojannawar"')
        parser.add_argument('--out', default=None,
                            help='Output path without extension (default: crm_backup_<users>_<time> here)')

    def handle(self, *args, **options):
        users = [find_user(token) for token in options['users']]
        self.stdout.write('Backing up CRM records for:')
        for u in users:
            self.stdout.write(f'  {u.username:15s} {u.get_full_name() or "-":30s} '
                              f'{"active" if u.is_active else "INACTIVE"}')
            # A short name can match a different person with the same first
            # name -- and backing up the wrong one looks exactly like success.
            owned = sum(M.objects.filter(owner=u).count() for M in (Account, Contact, Deal, Lead))
            if not owned and not Note.objects.filter(created_by=u).exists():
                self.stdout.write(self.style.WARNING(
                    f'    ^ owns no CRM records and wrote no notes -- is this the right person?'))

        # What they own, plus every deal they have touched in some way (a
        # note, a task, a stage move, an upload) even if someone else owns it.
        deals = Deal.objects.filter(
            Q(owner__in=users) | Q(notes__created_by__in=users) | Q(tasks__owner__in=users)
            | Q(tasks__created_by__in=users) | Q(stage_history__changed_by__in=users)
            | Q(attachments__uploaded_by__in=users)
        ).distinct()
        leads = Lead.objects.filter(
            Q(owner__in=users) | Q(notes__created_by__in=users) | Q(converted_deal__in=deals)
        ).distinct()
        # The contacts and accounts those deals hang off, so a restored deal
        # has its context.
        contacts = Contact.objects.filter(
            Q(owner__in=users) | Q(notes__created_by__in=users) | Q(deals__in=deals)
        ).distinct()
        accounts = Account.objects.filter(
            Q(owner__in=users) | Q(notes__created_by__in=users) | Q(deals__in=deals) | Q(contacts__in=contacts)
        ).distinct()
        notes = Note.objects.filter(
            Q(created_by__in=users) | Q(deal__in=deals) | Q(lead__in=leads)
            | Q(contact__in=contacts) | Q(account__in=accounts)
        ).distinct()
        tasks = DealTask.objects.filter(Q(deal__in=deals) | Q(owner__in=users) | Q(created_by__in=users)).distinct()
        history = DealStageHistory.objects.filter(deal__in=deals)
        attachments = DealAttachment.objects.filter(deal__in=deals)

        # Parents before children, so loaddata can restore in one pass.
        groups = [
            ('Accounts', accounts), ('Contacts', contacts), ('Deals', deals), ('Leads', leads),
            ('Notes', notes), ('Tasks', tasks), ('StageHistory', history), ('Attachments', attachments),
        ]
        data = {name: list(qs) for name, qs in groups}

        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        out = options['out'] or f'crm_backup_{"_".join(u.username for u in users)}_{stamp}'

        with open(f'{out}.json', 'w', encoding='utf-8') as f:
            f.write(serializers.serialize('json', [obj for objs in data.values() for obj in objs], indent=1))

        usernames = dict(User.objects.values_list('id', 'username'))
        stage_names = {d.stage_id: str(d.stage) for d in data['Deals']}
        with pd.ExcelWriter(f'{out}.xlsx') as xl:
            summary = [
                ('Backed up at', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                ('Users', ', '.join(f'{u.username} ({u.get_full_name()})' for u in users)),
                ('Scope', 'Records they own, every deal they added a note/task/stage move/file to, the '
                          'contacts and accounts of those deals, and all notes, tasks and stage history '
                          'on those records.'),
                ('Restore', f'python manage.py loaddata {os.path.basename(out)}.json  -- puts these records '
                            f'back exactly as they are in this backup (overwrites later changes to them).'),
            ] + [(name, f'{len(objs)} records') for name, objs in data.items()]
            pd.DataFrame(summary, columns=['', '']).to_excel(xl, sheet_name='Summary', index=False)

            for name, qs in groups:
                rows = list(qs.values())
                df = pd.DataFrame(rows)
                for col in ('owner_id', 'created_by_id', 'changed_by_id', 'uploaded_by_id'):
                    if col in df.columns:
                        df.insert(df.columns.get_loc(col) + 1, col[:-3] + '_username', df[col].map(usernames))
                if name == 'Deals' and 'stage_id' in df.columns:
                    df.insert(df.columns.get_loc('stage_id') + 1, 'stage_name', df['stage_id'].map(stage_names))
                df.to_excel(xl, sheet_name=name, index=False)

        self.stdout.write(self.style.SUCCESS('Backed up: ' + ', '.join(f'{len(o)} {n}' for n, o in data.items())))
        self.stdout.write(f'  {out}.xlsx  (to read)')
        self.stdout.write(f'  {out}.json  (to restore: python manage.py loaddata {out}.json)')
        if data['Attachments']:
            self.stdout.write(self.style.WARNING(
                f'  {len(data["Attachments"])} attachment records are listed, but the files themselves live '
                f'in the media folder -- back that folder up separately.'))
