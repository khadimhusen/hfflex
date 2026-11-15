"""The meetings list as an Excel file (real dates and numbers, so it can be sorted and filtered)."""
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HEADERS = ['No.', 'Meeting', 'Type', 'Date', 'Time', 'Location', 'Status', 'Attendees', 'Outside',
           'Action items', 'Open items', 'Created by']
WIDTHS = [14, 46, 13, 12, 8, 28, 9, 10, 9, 12, 11, 20]


def excel_filename(now=None):
    return f'meetings_{(now or datetime.now()).strftime("%Y%m%d_%H%M")}.xlsx'


def _person(user):
    if user is None:
        return ''
    return user.get_full_name().strip() or user.username


def generate_meetings_xlsx(response, meetings):
    """`meetings` is the list view's queryset (it carries the per-meeting counts)."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Meetings'
    sheet['A1'] = 'Minutes of meeting'
    sheet['A1'].font = Font(bold=True, size=14)
    sheet['A2'] = f'Generated: {datetime.now().strftime("%d/%m/%Y %H:%M")}'
    sheet['A2'].font = Font(color='808080', size=9)

    header_row = 4
    for column, label in enumerate(HEADERS, start=1):
        cell = sheet.cell(row=header_row, column=column, value=label)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='343A40')
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        sheet.column_dimensions[get_column_letter(column)].width = WIDTHS[column - 1]

    row_number = header_row
    for meeting in meetings:
        row_number += 1
        values = [
            meeting.number, meeting.title, meeting.meeting_type, meeting.meeting_date, meeting.meeting_time,
            meeting.location, meeting.status.title(),
            getattr(meeting, 'attendee_count', None), getattr(meeting, 'external_count', None),
            getattr(meeting, 'total_items', None), getattr(meeting, 'open_items', None),
            _person(meeting.created_by),
        ]
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(row=row_number, column=column, value=value)
            cell.alignment = Alignment(vertical='top', wrap_text=column in (2, 6))
            if column == 4:
                cell.number_format = 'dd/mm/yyyy'
            elif column == 5:
                cell.number_format = 'hh:mm'

    sheet.freeze_panes = sheet.cell(row=header_row + 1, column=3)
    sheet.auto_filter.ref = f'A{header_row}:{get_column_letter(len(HEADERS))}{max(row_number, header_row + 1)}'
    workbook.save(response)
