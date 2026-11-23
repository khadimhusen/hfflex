"""One-time clean-up of existing Printing rows (ItemProcess) by cylinder length.

    cylinder length >= 510  ->  PRINTING-2
    otherwise               ->  PRINTING-1

It does NOT change how new rows are saved: whoever creates an item process
still picks the machine by hand.

    python manage.py set_printing_machine_by_cylinder              # preview only
    python manage.py set_printing_machine_by_cylinder --apply      # really do it
    python manage.py set_printing_machine_by_cylinder --undo-from FILE

When a row moves to the other machine and its speed is still the old machine's
default speed, it gets the new machine's default speed instead (a speed that
someone set by hand is kept). Items with no cylinder length are left alone.
--apply first writes an undo file (row id, old machine id, old speed) that
--undo-from can put back. Existing jobs and schedules are not touched; only the
item's own Printing process template changes.
"""
import csv
import os
from collections import Counter
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from itemmaster.models import ItemProcess, Machine, Process

LONG_MACHINE = 'PRINTING-2'
SHORT_MACHINE = 'PRINTING-1'


class Command(BaseCommand):
    help = 'One-time: set the machine of existing Printing item processes from the cylinder length.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Really change the data (default: preview only).')
        parser.add_argument('--threshold', type=int, default=510,
                            help='Cylinder length at or above which PRINTING-2 is used (default 510).')
        parser.add_argument('--undo-file', default=None,
                            help='Where --apply writes the undo file (default: ~/printing-machine-undo-<time>.csv).')
        parser.add_argument('--undo-from', default=None, metavar='FILE',
                            help='Put back the machines and speeds saved in an undo file, then stop.')

    def handle(self, *args, **options):
        if options['undo_from']:
            return self.undo(options['undo_from'])

        process = self.get(Process, process='Printing')
        long_machine = self.get(Machine, machinename=LONG_MACHINE)
        short_machine = self.get(Machine, machinename=SHORT_MACHINE)
        threshold = options['threshold']

        rows = list(ItemProcess.objects.filter(process=process)
                    .select_related('machine', 'itemmaster').order_by('id'))
        changes, stats = [], Counter()
        for row in rows:
            stats['rows'] += 1
            length = row.itemmaster.cyl_length
            if length is None or length <= 0:
                stats['skipped: no cylinder length'] += 1
                continue
            target = long_machine if length >= threshold else short_machine
            if row.machine_id == target.id:
                stats['already correct'] += 1
                continue
            old = row.machine
            speed = row.speed
            if speed is not None and old is not None and speed == old.mode_speed:
                new_speed = target.mode_speed
                stats['speed reset to the new default'] += 1
            else:
                new_speed = speed
                stats['speed kept (set by hand)'] += 1
            stats[f'moved {old.machinename if old else "no machine"} -> {target.machinename}'] += 1
            changes.append((row, target, new_speed))

        self.stdout.write(f'Printing rows: {stats.pop("rows", 0)}  (threshold: cylinder length >= {threshold})')
        for key in sorted(stats):
            self.stdout.write(f'  {key}: {stats[key]}')
        self.stdout.write(f'Rows that will change: {len(changes)}')

        if not options['apply']:
            self.stdout.write(self.style.WARNING('Preview only -- nothing was changed. Add --apply to do it.'))
            return
        if not changes:
            self.stdout.write(self.style.SUCCESS('Nothing to do.'))
            return

        undo_file = os.path.expanduser(
            options['undo_file'] or f'~/printing-machine-undo-{datetime.now():%Y%m%d-%H%M%S}.csv')
        with open(undo_file, 'w', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['itemprocess_id', 'old_machine_id', 'old_speed'])
            for row, _target, _speed in changes:
                writer.writerow([row.pk, row.machine_id or '', '' if row.speed is None else row.speed])
        self.stdout.write(f'Undo file written: {undo_file}')

        with transaction.atomic():
            for row, target, new_speed in changes:
                row.machine = target
                row.speed = new_speed
            ItemProcess.objects.bulk_update([c[0] for c in changes], ['machine', 'speed'], batch_size=500)
        self.stdout.write(self.style.SUCCESS(f'Updated {len(changes)} rows.'))

    def undo(self, path):
        path = os.path.expanduser(path)
        with open(path, newline='') as handle:
            saved = list(csv.DictReader(handle))
        if not saved:
            raise CommandError(f'{path} has no rows')
        rows = {r.pk: r for r in ItemProcess.objects.filter(pk__in=[int(s['itemprocess_id']) for s in saved])}
        restored = []
        for s in saved:
            row = rows.get(int(s['itemprocess_id']))
            if row is None:
                continue
            row.machine_id = int(s['old_machine_id']) if s['old_machine_id'] else None
            row.speed = int(s['old_speed']) if s['old_speed'] != '' else None
            restored.append(row)
        with transaction.atomic():
            ItemProcess.objects.bulk_update(restored, ['machine', 'speed'], batch_size=500)
        self.stdout.write(self.style.SUCCESS(f'Restored {len(restored)} rows from {path}.'))

    def get(self, model, **lookup):
        try:
            return model.objects.get(**lookup)
        except model.DoesNotExist:
            raise CommandError(f'{model.__name__} not found: {lookup}')
