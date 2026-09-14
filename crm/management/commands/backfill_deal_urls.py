from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from crm.models import Deal
from ._import_utils import clean_str, read_export


class Command(BaseCommand):
    help = ("Fills Deal.url from a Zoho Deals export's 'URL 1' column, for imported deals that have no URL "
            "yet. Touches nothing else.")

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True, help='Zoho Deals export (Deals.xlsx / .csv)')
        parser.add_argument('--dry-run', action='store_true', help='Report what would be filled; save nothing.')

    @transaction.atomic
    def handle(self, *args, **options):
        df = read_export(options['file'])
        if 'URL 1' not in df.columns or 'Record Id' not in df.columns:
            raise CommandError(f"Expected 'Record Id' and 'URL 1' columns. Columns in the file: {list(df.columns)}")

        urls = {}
        for zoho_id, url in zip(df['Record Id'], df['URL 1']):
            zoho_id, url = clean_str(zoho_id), clean_str(url, 500)
            if zoho_id and url:
                urls[zoho_id] = url

        filled = already = 0
        found = Deal.objects.filter(zoho_record_id__in=urls.keys()).values_list('pk', 'zoho_record_id', 'url')
        for pk, zoho_id, current in found:
            if current:
                already += 1
                continue
            # A queryset update sets just this column and leaves updated_at
            # alone, so the Zoho importer won't mistake the deal for one that
            # was edited in the CRM.
            Deal.objects.filter(pk=pk).update(url=urls[zoho_id])
            filled += 1

        missing = len(urls) - filled - already
        summary = (f'Deal URLs — filled: {filled}, already had a URL: {already}, '
                   f'URL for a deal not in the CRM: {missing}')
        if options['dry_run']:
            transaction.set_rollback(True)
            summary = f'DRY RUN, nothing saved — {summary}'
        self.stdout.write(self.style.SUCCESS(summary))
