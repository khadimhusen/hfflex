"""The month sheet as an Excel file."""
import calendar
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .models import AttendanceDay

LETTER = {
    AttendanceDay.PRESENT: 'P', AttendanceDay.HALF: 'H', AttendanceDay.ABSENT: 'A', AttendanceDay.LEAVE: 'L',
    AttendanceDay.WEEKLY_OFF: 'WO', AttendanceDay.HOLIDAY: 'HD', AttendanceDay.REVIEW: '?',
}
FILL = {
    AttendanceDay.PRESENT: 'D4EDDA', AttendanceDay.HALF: 'FFF3CD', AttendanceDay.ABSENT: 'F8D7DA',
    AttendanceDay.LEAVE: 'D6EAF8', AttendanceDay.WEEKLY_OFF: 'E5E7E9', AttendanceDay.HOLIDAY: 'E5E7E9',
    AttendanceDay.REVIEW: 'FFE0B2',
}
TOTALS = [(AttendanceDay.PRESENT, 'Present'), (AttendanceDay.HALF, 'Half'), (AttendanceDay.ABSENT, 'Absent'),
          (AttendanceDay.LEAVE, 'Leave'), (AttendanceDay.WEEKLY_OFF, 'Wk off'), (AttendanceDay.HOLIDAY, 'Holiday'),
          (AttendanceDay.REVIEW, 'Review')]


def excel_filename(year, month):
    return f'attendance_{year}-{month:02d}.xlsx'


def generate_month_xlsx(response, year, month, sheet_rows):
    days = calendar.monthrange(year, month)[1]
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = f'{calendar.month_abbr[month]} {year}'
    sheet['A1'] = f'Worker attendance - {calendar.month_name[month]} {year}'
    sheet['A1'].font = Font(bold=True, size=14)
    sheet['A2'] = (f'Generated: {datetime.now().strftime("%d/%m/%Y %H:%M")}.   '
                   'P present, H half day, A absent, L paid leave, WO weekly off, HD holiday, ? needs review')
    sheet['A2'].font = Font(color='808080', size=9)

    header = ['Code', 'Worker'] + [str(d) for d in range(1, days + 1)] + [label for _, label in TOTALS] + [
        'Worked hrs', 'Overtime hrs', 'Paid days']
    head_row = 4
    for column, label in enumerate(header, start=1):
        cell = sheet.cell(row=head_row, column=column, value=label)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='343A40')
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        width = 9 if column == 1 else 26 if column == 2 else 4.2 if column <= 2 + days else 9
        sheet.column_dimensions[get_column_letter(column)].width = width
    for number, entry in enumerate(sheet_rows, start=head_row + 1):
        worker = entry['worker']
        sheet.cell(row=number, column=1, value=worker.emp_code or '')
        sheet.cell(row=number, column=2, value=worker.worker_name)
        for day in range(1, days + 1):
            row = entry['days'].get(day)
            cell = sheet.cell(row=number, column=2 + day, value=LETTER[row.status] if row else '')
            cell.alignment = Alignment(horizontal='center')
            if row:
                cell.fill = PatternFill('solid', fgColor=FILL[row.status])
        column = 3 + days
        for status, _ in TOTALS:
            sheet.cell(row=number, column=column, value=entry['counts'].get(status, 0))
            column += 1
        sheet.cell(row=number, column=column, value=round(entry['worked_minutes'] / 60, 2))
        sheet.cell(row=number, column=column + 1, value=round(entry['overtime_minutes'] / 60, 2))
        sheet.cell(row=number, column=column + 2, value=entry['paid_days'])
    sheet.freeze_panes = sheet.cell(row=head_row + 1, column=3)
    workbook.save(response)
