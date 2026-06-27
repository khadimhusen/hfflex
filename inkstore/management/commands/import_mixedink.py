# inkstore/management/commands/import_mixedink.py
import openpyxl
from django.core.management.base import BaseCommand
from inkstore.models import MixedInk


class Command(BaseCommand):
    help = 'Import mixed ink data from MIXEDINKDATA.xlsx'

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='Path to xlsx file')

    def handle(self, *args, **options):
        wb = openpyxl.load_workbook(options['file'], read_only=True, data_only=True)
        ws = wb['INK_STORE']

        created = 0
        skipped = 0

        for row in ws.iter_rows(min_row=3, values_only=True):  # skip header rows
            can_id = row[0]
            if not can_id or not isinstance(can_id, (int, float)):
                skipped += 1
                continue
            can_id = int(can_id)
            l_nw, a_nw, b_nw = row[1], row[2], row[3]
            l_ww, a_ww, b_ww = row[5], row[6], row[7]
            qty = row[9]

            if l_nw is None and l_ww is None:
                skipped += 1
                continue

            MixedInk.objects.filter(id=can_id).update(
                l_nw=l_nw, a_nw=a_nw, b_nw=b_nw,
                l_ww=l_ww, a_ww=a_ww, b_ww=b_ww,
                qty=qty)

            created += 1

        self.stdout.write(self.style.SUCCESS(f'Imported {created} cans, skipped {skipped} empty rows.'))
