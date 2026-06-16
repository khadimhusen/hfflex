from itemmaster.models import ItemProcess, Process
from material.models import Unit

# Map process name → unit name
PROCESS_UNIT_MAP = {
    'Printing'  : 'MTR.',
    'Lamination': 'MTR.',
    'Slitting'  : 'MTR.',
    'Pouching'  : 'NOS.',
}

total_updated = 0

for process_name, unit_name in PROCESS_UNIT_MAP.items():
    try:
        process = Process.objects.get(process=process_name)
    except Process.DoesNotExist:
        print(f"Process not found: {process_name}")
        continue

    try:
        unit = Unit.objects.get(unit=unit_name)
    except Unit.DoesNotExist:
        print(f"Unit not found: {unit_name}")
        continue

    count = ItemProcess.objects.filter(process=process).update(unit=unit)
    total_updated += count
    print(f"{process_name} → {unit_name}: {count} updated")

print(f"\nTotal updated: {total_updated}")
