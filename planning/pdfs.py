from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from django.http import HttpResponse
from datetime import datetime

from itemmaster.models import Machine
from .exports import schedule_rows, STATUS_LABEL
from .utils import shows_cylinder


def format_duration(d):
    if not d:
        return '—'
    total_secs = int(d.total_seconds())
    h = total_secs // 3600
    m = (total_secs % 3600) // 60
    return f'{h}h {m}m' if h else f'{m}m'


def format_variance(d):
    if not d:
        return '—'
    total_secs = int(d.total_seconds())
    sign       = '+' if total_secs >= 0 else '-'
    total_secs = abs(total_secs)
    h = total_secs // 3600
    m = (total_secs % 3600) // 60
    return f'{sign}{h:02d}:{m:02d}'


def columns(show_cylinder):
    """Header labels and widths (mm) -- landscape A4 leaves 277 mm."""
    headers = [
        '#', 'Job / Reason', 'Process', 'Qty', 'Speed',
        'Start', 'End', 'Makeready', 'Running', 'Downtime',
        'Est. Duration', 'Variance', 'Status', 'Material'
    ]
    widths = [8, 55, 20, 18, 15, 18, 18, 18, 16, 16, 18, 16, 14, 18]
    if show_cylinder:
        headers.insert(2, 'Cylinder')
        widths.insert(2, 16)
        widths[1] = 47          # the Job column gives up the room
    return headers, [w * mm for w in widths]


def machine_table(machine, cell_style):
    """Rows of one machine's table, header first: the last 5 completed, the
    running job, then the queue -- the same rows as the schedule page.

    Returns (table_data, col_widths, completed_rows, running_row_idx, hold_rows);
    the last three are row indexes to colour. The # column uses plain ASCII
    markers ('-' done, '>' running): the built-in PDF fonts have no check or
    play symbols."""
    show_cylinder = shows_cylinder(machine)
    headers, col_widths = columns(show_cylinder)

    def make_row(s, pos_label, status_label):
        if s.schedule_type == 'Idle':
            job_text = f'IDLE — {s.idle_reason}'
            process  = s.idle_notes or '—'
            cylinder = ''
        else:
            job_text = str(s.jobprocess) if s.jobprocess else '—'
            process  = str(s.jobprocess.process) if s.jobprocess else '—'
            cylinder = s.jobprocess.job.itemmaster.cylinder_status or 'Not Available'

        qty   = f'{s.qty} {s.unit}'   if s.qty   else '—'
        speed = f'{s.speed} {s.unit}/min' if s.speed else '—'
        start = s.start_time.strftime('%d/%m %H:%M') if s.start_time else '—'
        end   = s.end_time.strftime('%d/%m %H:%M')   if s.end_time   else '—'

        row = [
            pos_label,
            Paragraph(job_text, cell_style),
            Paragraph(process, cell_style),
            qty,
            speed,
            start,
            end,
            format_duration(s.makeready_duration),
            format_duration(s.running_duration),
            format_duration(s.downtime_duration),
            format_duration(s.estimated_duration),
            format_variance(s.time_variance),
            status_label,
            s.raw_material_status or '—',
        ]
        if show_cylinder:
            row.insert(2, Paragraph(cylinder, cell_style))
        return row

    table_data = [headers]
    completed_rows  = []
    hold_rows       = []
    running_row_idx = None

    for row_idx, (kind, s) in enumerate(schedule_rows(machine), start=1):
        pos_label = {'completed': '-', 'running': '>'}.get(kind, str(s.queue_position))
        table_data.append(make_row(s, pos_label, STATUS_LABEL[kind]))
        if kind == 'completed':
            completed_rows.append(row_idx)
        elif kind == 'running':
            running_row_idx = row_idx
        elif kind == 'hold':
            hold_rows.append(row_idx)

    if len(table_data) == 1:
        table_data.append(['—', Paragraph('No schedules', cell_style)] + [''] * (len(headers) - 2))

    return table_data, col_widths, completed_rows, running_row_idx, hold_rows


def generate_schedule_pdf(response, machines=None):
    """Write the schedule PDF to `response`: one page set per machine. With no
    `machines`, every active machine (the all-machines print)."""
    machines = list(machines) if machines is not None else list(Machine.objects.filter(active=True))

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        leftMargin=10*mm, rightMargin=10*mm,
        topMargin=15*mm, bottomMargin=15*mm,
    )

    title_style = ParagraphStyle(
        'title', fontSize=14, fontName='Helvetica-Bold',
        alignment=TA_LEFT, spaceAfter=4*mm
    )
    machine_style = ParagraphStyle(
        'machine', fontSize=11, fontName='Helvetica-Bold',
        alignment=TA_LEFT, spaceAfter=2*mm,
        textColor=colors.HexColor('#155724'),
    )
    date_style = ParagraphStyle(
        'date', fontSize=8, fontName='Helvetica',
        alignment=TA_LEFT, spaceAfter=3*mm,
        textColor=colors.grey,
    )
    cell_style = ParagraphStyle(
        'cell', fontSize=7, fontName='Helvetica',
        leading=9,
    )

    story = []

    # Title
    story.append(Paragraph('Machine Schedule', title_style))
    story.append(Paragraph(
        f'Generated: {datetime.now().strftime("%d/%m/%Y %H:%M")}',
        date_style
    ))
    story.append(Spacer(1, 3*mm))

    for i, machine in enumerate(machines):
        story.append(Paragraph(f'Machine: {machine.machinename}', machine_style))

        table_data, col_widths, completed_rows, running_row_idx, hold_rows = machine_table(machine, cell_style)

        table_style_cmds = [
            ('BACKGROUND',    (0, 0),  (-1, 0),  colors.HexColor('#343a40')),
            ('TEXTCOLOR',     (0, 0),  (-1, 0),  colors.white),
            ('FONTNAME',      (0, 0),  (-1, 0),  'Helvetica-Bold'),
            ('FONTSIZE',      (0, 0),  (-1, 0),  7),
            ('ALIGN',         (0, 0),  (-1, 0),  'CENTER'),
            ('FONTSIZE',      (0, 1),  (-1, -1), 7),
            ('FONTNAME',      (0, 1),  (-1, -1), 'Helvetica'),
            ('VALIGN',        (0, 0),  (-1, -1), 'MIDDLE'),
            ('GRID',          (0, 0),  (-1, -1), 0.3, colors.HexColor('#dee2e6')),
            ('TOPPADDING',    (0, 0),  (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0),  (-1, -1), 2),
            ('LEFTPADDING',   (0, 0),  (-1, -1), 2),
            ('RIGHTPADDING',  (0, 0),  (-1, -1), 2),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ]

        for r in completed_rows:
            table_style_cmds.append(('TEXTCOLOR', (0, r), (-1, r), colors.grey))

        if running_row_idx:
            table_style_cmds.append(('BACKGROUND', (0, running_row_idx), (-1, running_row_idx), colors.HexColor('#d4edda')))
            table_style_cmds.append(('FONTNAME',   (0, running_row_idx), (-1, running_row_idx), 'Helvetica-Bold'))

        for r in hold_rows:
            table_style_cmds.append(('BACKGROUND', (0, r), (-1, r), colors.HexColor('#f8d7da')))

        t = Table(table_data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle(table_style_cmds))
        story.append(t)

        if i < len(machines) - 1:
            story.append(PageBreak())

    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(colors.grey)
        canvas.drawRightString(
            landscape(A4)[0] - 10*mm,
            8*mm,
            f'Page {canvas.getPageNumber()}'
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
