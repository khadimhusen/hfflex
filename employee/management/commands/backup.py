import os
import time
import io
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.apps import apps


class Command(BaseCommand):
    help = 'Backup all Django models to JSON files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='backups',
            help='Base directory to store backups (default: backups/)',
        )
        parser.add_argument(
            '--app',
            type=str,
            default=None,
            help='Backup only a specific app (e.g. --app=order)',
        )

    def handle(self, *args, **options):
        base_dir = options['output_dir']
        filter_app = options['app']
        date_str = time.strftime("%Y-%m-%d")
        backup_folder = os.path.join(base_dir, date_str)

        os.makedirs(backup_folder, exist_ok=True)

        all_models = apps.get_models()
        success_count = 0
        fail_count = 0

        for model in all_models:
            app_label = model._meta.app_label
            model_name = model._meta.model_name

            if filter_app and app_label != filter_app:
                continue

            backup_file = os.path.join(backup_folder, f'{app_label}_{model_name}.json')

            try:
                # Capture into StringIO buffer, then write with explicit UTF-8
                buffer = io.StringIO()
                call_command(
                    'dumpdata',
                    f'{app_label}.{model_name}',
                    format='json',
                    indent=2,
                    verbosity=0,
                    stdout=buffer,
                )
                with open(backup_file, 'w', encoding='utf-8') as f:
                    f.write(buffer.getvalue())

                self.stdout.write(self.style.SUCCESS(f'  ✔  {app_label}.{model_name}'))
                success_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ✘  {app_label}.{model_name} — {e}'))
                fail_count += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Backup complete → {backup_folder}  '
            f'({success_count} succeeded, {fail_count} failed)'
        ))