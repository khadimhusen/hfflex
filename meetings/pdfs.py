"""The minutes of one meeting as a PDF, on the company letterhead.

Built with the PDF library's standard Helvetica, so it prints English (Latin)
text; characters from other scripts need a font that has them."""
import io
import os
import re
from xml.sax.saxutils import escape

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from company.letterhead import LEGACY_LOGO_URL, letterhead

from .richtext import html_to_flowables

LOGO_WIDTH = 16 * mm
LOGO_ASPECT = 365 / 425            # hflogo.png is 365 x 425
MARGIN_X = 15 * mm
HEADER_RULE_FROM_TOP = 34 * mm

BODY = ParagraphStyle('body', fontName='Helvetica', fontSize=9.5, leading=13)
SMALL = ParagraphStyle('small', parent=BODY, fontSize=8.5, leading=11, textColor=colors.HexColor('#555555'))
CELL = ParagraphStyle('cell', parent=BODY, fontSize=8.5, leading=11)
CELL_HEAD = ParagraphStyle('cellhead', parent=CELL, fontName='Helvetica-Bold', textColor=colors.white)
HEADING = ParagraphStyle('heading', parent=BODY, fontName='Helvetica-Bold', fontSize=10.5, spaceBefore=10,
                         spaceAfter=3, textColor=colors.HexColor('#155724'))
TITLE = ParagraphStyle('title', parent=BODY, fontName='Helvetica-Bold', fontSize=15, leading=19, spaceAfter=2)
MEETING_TITLE = ParagraphStyle('mtitle', parent=BODY, fontName='Helvetica-Bold', fontSize=12, leading=15,
                               spaceAfter=6)


def pdf_filename(meeting):
    slug = re.sub(r'[^A-Za-z0-9]+', '_', meeting.title).strip('_')[:40]
    return f'{meeting.number}_{slug}.pdf' if slug else f'{meeting.number}.pdf'


def _text(value):
    """Plain text -> PDF paragraph markup: escaped, line breaks kept."""
    return '<br/>'.join(escape(line) for line in (value or '').splitlines()) or '&nbsp;'


def _para(value, style=BODY):
    return Paragraph(_text(value), style)


def logo_path(lh):
    """The company's logo file for the PDF, or None (a missing file never breaks the PDF)."""
    company = lh.company
    if company is not None and getattr(company, 'logo', None):
        path = company.logo.path
    elif getattr(lh, 'logo_url', '') == LEGACY_LOGO_URL:
        path = os.path.join(settings.BASE_DIR, 'static', 'images', 'hflogo.png')
    else:
        path = None
    return path if path and os.path.exists(path) else None


def _person(user):
    if user is None:
        return ''
    return user.get_full_name().strip() or user.username


def build_minutes_pdf(meeting):
    """The PDF as bytes."""
    lh = letterhead()
    logo = logo_path(lh)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=MARGIN_X, rightMargin=MARGIN_X,
                            topMargin=HEADER_RULE_FROM_TOP + 6 * mm, bottomMargin=18 * mm,
                            title=f'{meeting.number} {meeting.title}', author=lh.name)

    def page_furniture(canvas, document):
        canvas.saveState()
        width, height = A4
        top = height - 12 * mm
        text_x = MARGIN_X
        if logo:
            logo_h = LOGO_WIDTH / LOGO_ASPECT
            try:
                canvas.drawImage(logo, MARGIN_X, top - logo_h, width=LOGO_WIDTH, height=logo_h, mask='auto',
                                 preserveAspectRatio=True)
                text_x = MARGIN_X + LOGO_WIDTH + 4 * mm
            except Exception:                       # an unreadable logo is skipped, not fatal
                pass
        canvas.setFont('Helvetica-Bold', 13)
        canvas.drawString(text_x, top - 5 * mm, lh.title_name)
        canvas.setFont('Helvetica', 8)
        lines = [lh.address_line1, lh.address_line2,
                 '   '.join(part for part in (
                     f'Phone: {lh.phone}' if lh.phone else '', f'Email: {lh.email}' if lh.email else '',
                     f'GSTIN: {lh.gstin}' if lh.gstin else '') if part)]
        y = top - 10 * mm
        for line in (l for l in lines if l):
            canvas.drawString(text_x, y, line)
            y -= 4 * mm
        canvas.setStrokeColor(colors.HexColor('#999999'))
        canvas.setLineWidth(0.6)
        canvas.line(MARGIN_X, height - HEADER_RULE_FROM_TOP, width - MARGIN_X, height - HEADER_RULE_FROM_TOP)
        canvas.setFont('Helvetica', 7.5)
        canvas.setFillColor(colors.HexColor('#777777'))
        canvas.drawString(MARGIN_X, 9 * mm, f'{meeting.number}  -  prepared by {_person(meeting.created_by) or "-"}')
        canvas.drawRightString(width - MARGIN_X, 9 * mm, f'Page {document.page}')
        canvas.restoreState()

    story = [Paragraph('Minutes of meeting', TITLE)]
    if not meeting.is_final:
        story.append(Paragraph('<font color="#b26a00">DRAFT - not yet finalised</font>', SMALL))
    story += [Spacer(1, 2 * mm), Paragraph(escape(meeting.title), MEETING_TITLE)]

    when = meeting.meeting_date.strftime('%d/%m/%Y')
    if meeting.meeting_time:
        when += f'  {meeting.meeting_time.strftime("%H:%M")}'
    facts = Table([
        [Paragraph('<b>Meeting no.</b>', CELL), Paragraph(escape(meeting.number), CELL),
         Paragraph('<b>Type</b>', CELL), Paragraph(escape(meeting.meeting_type), CELL)],
        [Paragraph('<b>Date and time</b>', CELL), Paragraph(escape(when), CELL),
         Paragraph('<b>Location</b>', CELL), Paragraph(escape(meeting.location or '-'), CELL)],
    ], colWidths=[28 * mm, 52 * mm, 24 * mm, 76 * mm])
    facts.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#cccccc')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f3f3')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f3f3f3')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(facts)

    attendees = list(meeting.attendees.all())
    inside = [a.name for a in attendees if a.user_id is not None]
    outside = [a.name + (f' ({a.organisation})' if a.organisation else '') for a in attendees if a.user_id is None]
    story.append(Paragraph('Present', HEADING))
    story.append(_para(', '.join(inside) or '-'))
    if outside:
        story.append(Spacer(1, 1.5 * mm))
        story.append(Paragraph('<b>Also present (outside):</b> ' + escape(', '.join(outside)), BODY))

    agenda = html_to_flowables(meeting.agenda, BODY)
    if agenda:
        story += [Paragraph('Agenda', HEADING), *agenda]
    story += [Paragraph('Minutes', HEADING), *(html_to_flowables(meeting.minutes, BODY) or [_para('-')])]

    items = list(meeting.action_items.select_related('owner', 'task'))
    if items:
        rows = [[Paragraph(label, CELL_HEAD) for label in ('#', 'Action', 'Owner', 'Due', 'Priority', 'Status')]]
        for number, item in enumerate(items, start=1):
            rows.append([
                Paragraph(str(number), CELL), Paragraph(_text(item.description), CELL),
                Paragraph(escape(_person(item.owner)), CELL), Paragraph(item.due_date.strftime('%d/%m/%Y'), CELL),
                Paragraph(escape(item.priority.title()), CELL), Paragraph(item.status.title(), CELL),
            ])
        table = Table(rows, colWidths=[8 * mm, 76 * mm, 36 * mm, 22 * mm, 20 * mm, 18 * mm], repeatRows=1)   # = 180 mm
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#343a40')),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#cccccc')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(KeepTogether([Paragraph('Action items', HEADING), table]))

    if meeting.next_meeting_at:
        story += [Spacer(1, 3 * mm),
                  Paragraph(f'<b>Next meeting:</b> {meeting.next_meeting_at.strftime("%d/%m/%Y %H:%M")}', BODY)]
    if meeting.is_final and meeting.finalised_at:
        story += [Spacer(1, 3 * mm),
                  Paragraph(f'Finalised on {meeting.finalised_at.strftime("%d/%m/%Y %H:%M")}'
                            + (f' by {escape(_person(meeting.finalised_by))}' if meeting.finalised_by else ''), SMALL)]

    doc.build(story, onFirstPage=page_furniture, onLaterPages=page_furniture)
    return buffer.getvalue()
