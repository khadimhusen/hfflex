"""One machine's schedule as data, and as an Excel file.

schedule_rows() decides WHICH rows a machine's schedule shows (the PDF and the
Excel file both use it, so they never differ); each format then renders them.
"""
import re
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .models import MachineSchedule
from .utils import shows_cylinder

COMPLETED_SHOWN = 5          # same as the schedule page
_RELATED = ('jobprocess__job__itemmaster', 'jobprocess__process', 'idle_reason', 'unit')


def schedule_rows(machine):
    """[(kind, MachineSchedule)] in schedule order: the newest completed rows
    (oldest first), the running job, then the queue. kind is one of
    'completed', 'running', 'pending', 'hold', 'idle'."""
    completed_qs = (
        MachineSchedule.objects
        .filter(machine=machine, queue_position=-1)
        .select_related(*_RELATED)
        .order_by('-end_time', '-id')[:COMPLETED_SHOWN]
    )
    completed = sorted(completed_qs, key=lambda x: x.end_time or x.created)

    running = (
        MachineSchedule.objects
        .filter(machine=machine, queue_position=0)
        .select_related(*_RELATED)
        .first()
    )

    queue = (
        MachineSchedule.objects
        .filter(machine=machine, queue_position__gt=0)
        .select_related(*_RELATED)
        .order_by('queue_position')
    )

    rows = [('completed', s) for s in completed]
    if running:
        rows.append(('running', running))
    for s in queue:
        kind = 'hold' if s.status == 'Hold' else ('idle' if s.schedule_type == 'Idle' else 'pending')
        rows.append((kind, s))
    return rows


STATUS_LABEL = {'completed': 'Completed', 'running': 'Running', 'pending': 'Pending',
                'hold': 'Hold', 'idle': 'Idle'}

_FILL = {
    'running': PatternFill('solid', fgColor='D4EDDA'),
    'hold': PatternFill('solid', fgColor='F8D7DA'),
}
_HEADER_FILL = PatternFill('solid', fgColor='343A40')


def _minutes(delta):
    return round(delta.total_seconds() / 60) if delta is not None else None


def excel_filename(machine, now=None):
    name = re.sub(r'[^A-Za-z0-9]+', '_', machine.machinename).strip('_') or 'machine'
    return f'schedule_{name}_{(now or datetime.now()).strftime("%Y%m%d_%H%M")}.xlsx'


def generate_schedule_xlsx(response, machine):
    """Write one machine's schedule to `response` as an .xlsx. Numbers and
    dates are real Excel values (sortable, filterable); durations are
    [h]:mm and the variance is signed minutes."""
    show_cylinder = shows_cylinder(machine)

    headers = ['#', 'Job / Reason']
    if show_cylinder:
        headers.append('Cylinder')
    headers += ['Process', 'Qty', 'Unit', 'Speed', 'Start', 'End', 'Makeready', 'Running', 'Downtime',
                'Est. Duration', 'Variance (min)', 'Status', 'Material']
    widths = {'#': 6, 'Job / Reason': 48, 'Cylinder': 14, 'Process': 20, 'Qty': 11, 'Unit': 8, 'Speed': 8,
              'Start': 17, 'End': 17, 'Makeready': 11, 'Running': 10, 'Downtime': 10, 'Est. Duration': 13,
              'Variance (min)': 14, 'Status': 11, 'Material': 14}

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = re.sub(r'[\[\]:*?/\\]', '-', machine.machinename)[:31] or 'Schedule'

    sheet['A1'] = f'Machine Schedule - {machine.machinename}'
    sheet['A1'].font = Font(bold=True, size=14)
    sheet['A2'] = f'Generated: {datetime.now().strftime("%d/%m/%Y %H:%M")}'
    sheet['A2'].font = Font(color='808080', size=9)

    header_row = 4
    for col, label in enumerate(headers, start=1):
        cell = sheet.cell(row=header_row, column=col, value=label)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        sheet.column_dimensions[get_column_letter(col)].width = widths[label]

    duration_cols = {'Makeready', 'Running', 'Downtime', 'Est. Duration'}
    row_no = header_row
    for kind, s in schedule_rows(machine):
        row_no += 1
        is_idle = s.schedule_type == 'Idle'
        values = {
            '#': s.queue_position if s.queue_position > 0 else None,
            'Job / Reason': (f'IDLE - {s.idle_reason}' if is_idle else (str(s.jobprocess) if s.jobprocess else '')),
            'Process': ((s.idle_notes or '') if is_idle else (str(s.jobprocess.process) if s.jobprocess else '')),
            'Qty': float(s.qty) if s.qty is not None else None,
            'Unit': str(s.unit) if s.unit else None,
            'Speed': s.speed,
            'Start': s.start_time,
            'End': s.end_time,
            'Makeready': s.makeready_duration,
            'Running': s.running_duration,
            'Downtime': s.downtime_duration,
            'Est. Duration': s.estimated_duration,
            'Variance (min)': _minutes(s.time_variance),
            'Status': STATUS_LABEL[kind],
            'Material': None if is_idle else s.raw_material_status,
        }
        if show_cylinder:
            values['Cylinder'] = None if is_idle else (s.jobprocess.job.itemmaster.cylinder_status or 'Not Available')

        for col, label in enumerate(headers, start=1):
            cell = sheet.cell(row=row_no, column=col, value=values[label])
            cell.alignment = Alignment(vertical='top', wrap_text=label in ('Job / Reason', 'Process'))
            if label in ('Start', 'End'):
                cell.number_format = 'dd/mm/yyyy hh:mm'
            elif label in duration_cols:
                cell.number_format = '[h]:mm'
            if kind in _FILL:
                cell.fill = _FILL[kind]
            elif kind == 'completed':
                cell.font = Font(color='808080')
            if kind == 'running':
                cell.font = Font(bold=True)

    if row_no == header_row:
        sheet.cell(row=header_row + 1, column=2, value='No schedules')

    sheet.freeze_panes = sheet.cell(row=header_row + 1, column=3)
    sheet.auto_filter.ref = f'A{header_row}:{get_column_letter(len(headers))}{max(row_no, header_row + 1)}'
    workbook.save(response)
