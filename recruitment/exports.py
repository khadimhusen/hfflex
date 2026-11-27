from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font

from . import services

HEADERS = [
    'Opening', 'Name', 'Mobile', 'Email', 'Location', 'Company', 'Designation', 'Experience (yrs)',
    'Current salary', 'Expected salary', 'Notice (days)', 'Source', 'Stage', 'Interview score', 'Offered salary',
    'Offer date', 'Joining date', 'Rejection reason', 'Added on',
]


def excel_filename():
    return f'candidates-{timezone.now().date():%Y%m%d}.xlsx'


def generate_candidates_xlsx(stream, candidates):
    """`candidates` should come with interviews prefetched (the viewset does it)."""
    wb = Workbook()
    ws = wb.active
    ws.title = 'Candidates'
    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for c in candidates:
        ws.append([
            c.opening.number, c.name, c.mobile, c.email, c.location, c.current_company, c.current_designation,
            float(c.experience_years) if c.experience_years is not None else None,
            c.current_salary, c.expected_salary, c.notice_period_days, c.source, c.get_stage_display(),
            services.candidate_score(c), c.offered_salary, c.offer_date, c.joining_date, c.rejection_reason,
            c.created_at.date(),
        ])
    for column, width in zip('ABCDEFGHIJKLMNOPQRS', (13, 24, 14, 26, 16, 24, 24, 10, 12, 12, 10, 14, 12, 10, 12,
                                                    12, 12, 30, 12)):
        ws.column_dimensions[column].width = width
    ws.freeze_panes = 'A2'
    wb.save(stream)
