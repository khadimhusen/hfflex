from django.core.management import call_command
from django.apps import apps
import os
import time

# Replace 'backup_folder' with the path to your backup folder

backup_folder = f'backup_folder/{time.strftime("%Y-%m-%d")}'

# Create the backup folder if it doesn't exist
if not os.path.exists(backup_folder):
    os.makedirs(backup_folder)

# Get all models in your Django app
all_models = apps.get_models()

# Loop through each model and create a JSON backup
for model in all_models:
    app_label = model._meta.app_label
    model_name = model._meta.model_name
    backup_file = f'{backup_folder}/{app_label}_{model_name}_backup.json'

    # Run the dumpdata command for the specific model and save it as a JSON file
    call_command('dumpdata', f'{app_label}.{model_name}', '--output=' + backup_file, '--format=json')
