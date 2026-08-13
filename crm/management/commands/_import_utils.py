from django.contrib.auth.models import User
import os
from datetime import datetime
import pandas as pd


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


def write_log_file(command_name, log_lines, summary_line):
    """Writes the import log to a timestamped file under crm/import_logs/."""
    log_dir = os.path.join('crm', 'import_logs')
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = os.path.join(log_dir, f'{command_name}_{timestamp}.log')

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


def clean_datetime(value):
    if value is None or str(value) == 'nan' or str(value).strip() == '':
        return None
    parsed = pd.to_datetime(value, errors='coerce')
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()
