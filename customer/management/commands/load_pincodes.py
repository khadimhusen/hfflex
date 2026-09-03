"""Loads customer/data/india_pincodes.csv into the Pincode table.

That CSV is a one-time, offline-built reduction of India Post's public
pincode directory (https://github.com/harshvardhaniimi/IndiaPIN,
data-raw/pincode.csv -- ~157k individual post offices) down to one row
per unique 6-digit pincode: HO/PO office name preferred over a small
BO for place_name, coordinates averaged across that pincode's offices.
No network access needed at load time -- the CSV is committed to the repo.

Run once per environment (including production, after this migrates)
to populate the table CustomerViewSet.nearby queries against:

    manage.py load_pincodes

Safe to re-run -- does a full replace, not an incremental import.
"""
import csv
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from customer.models import Pincode

CSV_PATH = os.path.join(settings.BASE_DIR, 'customer', 'data', 'india_pincodes.csv')


class Command(BaseCommand):
    help = 'Load/refresh the India pincode -> lat/lng lookup table from customer/data/india_pincodes.csv'

    def handle(self, *args, **options):
        with open(CSV_PATH, encoding='utf-8') as f:
            rows = list(csv.DictReader(f))

        objs = [
            Pincode(
                code=int(row['pincode']),
                place_name=row['place_name'],
                district=row['district'],
                state=row['state'],
                latitude=row['latitude'],
                longitude=row['longitude'],
            )
            for row in rows
        ]

        with transaction.atomic():
            Pincode.objects.all().delete()
            Pincode.objects.bulk_create(objs, batch_size=2000)

        self.stdout.write(self.style.SUCCESS(f'Loaded {len(objs)} pincodes.'))
