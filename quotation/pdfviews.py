"""
RECOMMENDED ARCHITECTURE FOR FIXED HEADER + FOOTER + FLOWABLE BODY
===================================================================

Structure:
  - draw_header(canvas, doc)  →  draws letterhead, company info, customer info
  - draw_footer(canvas, doc)  →  draws page number, signature strip
  - onPage = lambda c, d: (draw_header(c,d), draw_footer(c,d))
  - Frame occupies only the middle band
  - story[] contains all flowable content — ReportLab handles page breaks automatically

Page layout (A4 = 842pt tall):
  ┌─────────────────────────────┐  ← top (842)
  │   HEADER  (fixed, ~160pt)   │  drawn by draw_header()
  ├─────────────────────────────┤  ← 682
  │                             │
  │   BODY FRAME  (flowable)    │  Frame(x=15, y=55, w=550, h=627)
  │   Story goes here           │
  │                             │
  ├─────────────────────────────┤  ← 55
  │   FOOTER  (fixed, ~50pt)    │  drawn by draw_footer()
  └─────────────────────────────┘  ← bottom (0)
"""

import io
import os

from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.conf import settings

from reportlab.lib import colors
from reportlab.lib.colors import orange, yellow, black
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas as PdfCanvas
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Table, TableStyle, Image,
)
import reportlab.rl_config

from myproject.access import accessview
from .models import Quotation

# ── Font registration ─────────────────────────────────────────────────────────
reportlab.rl_config.warnOnMissingFontGlyphs = 0
pdfmetrics.registerFont(TTFont('times', 'times.ttf'))
pdfmetrics.registerFont(TTFont('arial', 'Arial.ttf'))
pdfmetrics.registerFont(TTFont('timesbd', 'timesbd.ttf'))
pdfmetrics.registerFont(TTFont(
    'LohitDevanagari',
    os.path.join(settings.BASE_DIR, 'static/fonts/Lohit-Devanagari.ttf'),
))

# ── Page geometry ─────────────────────────────────────────────────────────────
W, H = A4
MARGIN_L = 15
MARGIN_R = 35
HEADER_H = 190  # pt reserved at top for letterhead + customer block
FOOTER_H = 55  # pt reserved at bottom for page number / signature

FRAME_X = MARGIN_L
FRAME_Y = FOOTER_H
FRAME_W = W - MARGIN_L - MARGIN_R
FRAME_H = H - HEADER_H - FOOTER_H


# ── Numbered canvas ───────────────────────────────────────────────────────────
class NumberedCanvas(PdfCanvas):
    """Gives access to total page count so footer can print 'Page X of Y'."""

    def __init__(self, *args, **kwargs):
        PdfCanvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_number(total)
            PdfCanvas.showPage(self)
        PdfCanvas.save(self)

    def _draw_page_number(self, total):
        self.setFont('arial', 9)
        self.setFillColorRGB(0.3, 0.3, 0.3)
        self.drawRightString(W - MARGIN_R, 20, f'Page {self._pageNumber} of {total}')
        if self._pageNumber < total:
            self.setFillColorRGB(0.4, 0.4, 0.4)
            self.setStrokeColorRGB(0.7, 0.7, 0.7)
            self.setLineWidth(0.5)
            self.line(MARGIN_L, 45, W - MARGIN_R, 45)
            self.drawCentredString(W / 2, 33, 'Continued on next page...')
        self.setFillColor(black)
        self.setStrokeColor(black)


# ── Helper ────────────────────────────────────────────────────────────────────
def _drawpath(c, start, nodes):
    path = c.beginPath()
    path.moveTo(*start)
    for node in nodes:
        path.lineTo(*node)
    c.drawPath(path, stroke=1, fill=1)


# ── Main view ─────────────────────────────────────────────────────────────────
@login_required(login_url='/login/')
@accessview
def quotepdf(_, id):
    quote = get_object_or_404(Quotation, id=id)
    buffer = io.BytesIO()

    styles = getSampleStyleSheet()
    styleN = styles['BodyText']
    styleN.leading = 11

    # ── Header callback — called once per page automatically ──────────────────
    def draw_header(canvas, doc):
        canvas.saveState()

        # Decorative corner triangles
        canvas.setFillColor(yellow);
        canvas.setStrokeColor(yellow)
        _drawpath(canvas, (0, H), [(80, H), (0, H - 80)])
        canvas.setFillColor(orange);
        canvas.setStrokeColor(orange)
        _drawpath(canvas, (0, H), [(73, H), (0, H - 73)])

        # Right green strip
        canvas.setFillColorRGB(0.7, 0.9, 0);
        canvas.setStrokeColorRGB(0.7, 0.9, 0)
        _drawpath(canvas, [W - 30, H], [(W, H), (W, 0), (W - 30, 0)])

        # "H F FLEX" text on strip
        canvas.rotate(90)
        canvas.setFont('times', 14);
        canvas.setFillColorRGB(0.1, 0.4, 0.6)
        canvas.drawCentredString(450, -580, '   H F FLEX  ' * 10)
        canvas.rotate(-90)

        # Company name
        canvas.setFillColorRGB(0.1, 0.1, 0.1)
        canvas.setFont('timesbd', 25)
        canvas.drawCentredString(W / 2 - 99, H - 33.5, 'H F Flex Pvt. Ltd.')
        canvas.setFillColorRGB(0.80, 0, 0)
        canvas.drawCentredString(W / 2 - 100, H - 34, 'H F Flex Pvt. Ltd.')

        # Company address
        canvas.setFillColorRGB(0, 0.2, 0.5);
        canvas.setFont('arial', 9)
        cx = W / 2 - 100
        canvas.drawCentredString(cx, H - 45, '25, Lucky Lark Textile Park, Gardi, Vita')
        canvas.drawCentredString(cx, H - 57, 'Tal- Khanapur, Dist- Sangli, Maharashtra-415311')
        canvas.drawCentredString(cx, H - 70, f'Contact:- {quote.createdby.profile.mobile}')
        canvas.drawCentredString(cx, H - 84, 'Email:- hfflexpvtltd@gmail.com  |  www.hfflex.co.in')

        # Quotation meta (top right)
        canvas.setFont('arial', 10);
        canvas.setFillColorRGB(0.0, 0.2, 0.5)
        rx = W - MARGIN_R - 145
        canvas.drawRightString(rx, H - 30, 'Quotation No:- ')
        canvas.setFont('arial', 14)
        canvas.drawString(rx, H - 30, f'# {str(quote.id).zfill(6)}')
        canvas.setFont('arial', 10)
        canvas.drawRightString(rx, H - 45, 'Date:- ')
        canvas.drawString(rx, H - 45, quote.quotedate.strftime('%d/%m/%Y'))
        canvas.drawRightString(rx, H - 60, 'Created By:- ')
        canvas.drawString(rx, H - 60, f'{quote.createdby} ({quote.createdby.profile.mobile})')
        canvas.drawRightString(rx, H - 75, 'Company GST:- ')
        canvas.drawString(rx, H - 75, '27AADCH3462K1ZF')
        canvas.drawRightString(rx, H - 90, 'Company CIN:- ')
        canvas.drawString(rx, H - 90, 'U74900PN2014PTC150332')

        # Divider below letterhead
        canvas.setFillColor(black);
        canvas.setStrokeColor(black)
        _drawpath(canvas, [MARGIN_L, H - 105], [(W - MARGIN_R, H - 105)])

        # ── Customer block (drawn as canvas text, always at same Y) ──────────
        canvas.setFont('arial', 9);
        canvas.setFillColorRGB(0.1, 0.1, 0.1)
        y = H - 118
        canvas.drawString(MARGIN_L, y, f'Customer : {quote.partyname.upper()}')
        # canvas.drawRightString(W - MARGIN_R, y, f'Date : {quote.quotedate.strftime("%d/%m/%Y")}')
        canvas.drawString(MARGIN_L, y - 13, f'Address  : {quote.add or "-"}')
        canvas.drawString(MARGIN_L, y - 26, f'Contact  : {quote.contact or "-"}')

        # Divider below customer block
        canvas.setStrokeColorRGB(0.7, 0.7, 0.7);
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN_L, H - 152, W - MARGIN_R, H - 152)

        canvas.restoreState()

    # ── Footer callback ───────────────────────────────────────────────────────
    def draw_footer(canvas, doc):
        # Page number is handled by NumberedCanvas._draw_page_number()
        # Add anything static here — e.g. company tagline, confidentiality note
        canvas.saveState()
        canvas.setFont('arial', 7)
        canvas.setFillColorRGB(0.5, 0.5, 0.5)
        canvas.drawCentredString(W / 2, 8, 'H F Flex Pvt. Ltd. | Confidential')
        canvas.restoreState()

    def on_page(canvas, doc):
        draw_header(canvas, doc)
        draw_footer(canvas, doc)

    # ── Document + frame ──────────────────────────────────────────────────────
    frame = Frame(FRAME_X, FRAME_Y, FRAME_W, FRAME_H, id='body', showBoundary=False)
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        pageTemplates=[PageTemplate(id='main', frames=[frame], onPage=on_page)],
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=HEADER_H,
        bottomMargin=FOOTER_H,
    )

    # ── Story (all flowable content) ──────────────────────────────────────────
    story = []

    # ── Item table ────────────────────────────────────────────────────────────
    tabelheader = [
        '#',
        Paragraph('Description', styleN),
        Paragraph('Cylinder<br/>Detail', styleN),
        Paragraph('Cylinder<br/>Cost', styleN),
        Paragraph('Material<br/>Rate', styleN),
        Paragraph('Pouch<br/>Per<br/>Kg.', styleN),
        Paragraph('Per Pouch<br/>Cost.', styleN),
        Paragraph('MOQ', styleN),
        Paragraph('Material<br/>Cost', styleN),
    ]
    data = [tabelheader]

    for i, item in enumerate(quote.quotationitems.all(), 1):
        itemdesc = (
            f'{item.jobname}<br/>Size:- {item.dimension}<br/>'
            f'{item.structure}<br/>Supply :- {item.supply}'
        )
        para = Paragraph(f'<font name=arial size=8>{itemdesc}</font>', styleN)

        if item.cyl_rate and item.no_of_cyl:
            cyl_detail = Paragraph(f'<font size=8>Rs.{round(item.cyl_rate)} x {item.no_of_cyl}Nos.</font>', styleN)
            cyl_cost = Paragraph(f'<font size=8>Rs.{round(item.item_cylinder_cost, 0)}</font>', styleN)
        else:
            cyl_detail = Paragraph('<font size=8>-</font>', styleN)
            cyl_cost = Paragraph('<font size=8>-</font>', styleN)

        mat_rate = (
            Paragraph(f'<font size=8>Rs.{round(item.material_rate, 1)}</font>', styleN)
            if item.material_rate else Paragraph('<font size=8>-</font>', styleN)
        )

        data.append([
            str(i), para, cyl_detail, cyl_cost, mat_rate,
            Paragraph(f'<font size=8>{item.pouch_per_kg or "-"}</font>', styleN),
            Paragraph(f'<font size=8>Rs. {item.per_pouch_cost or "-"}</font>', styleN),
            Paragraph(f'<font size=8>{item.moq} {item.unit}</font>', styleN),
            Paragraph(f'<font size=8>Rs.{round(item.itemtotalcost)}</font>', styleN),
        ])

    # ── Footer rows ───────────────────────────────────────────────────────────
    sbibank = (
        '<font size=8>Bank Name:- State bank of India<br/>'
        'Branch:- VITA<br/>'
        'Account Name:- H F FLEX PVT. LTD.<br/>'
        'Account No:- 38244070864<br/>'
        'IFS Code:- SBIN0000285</font>'
        '<br/><font name="LohitDevanagari" size=8>'
        'कोटेशन में दीए हुए बैंक अकाउंट के अलावा कीसी और बैंक अकाउंट पर पेमेंट ना करें।'
        '</font>'
    )
    sbibankdetail = Paragraph(sbibank, styleN)

    sig = Image(
        'static/images/husensign.png' if quote.approvedby.username == 'khadimhusen'
        else 'static/images/firojsign.png',
        1.2 * inch, 1.2 * inch,
    )

    item_count = len(data) - 1  # items already appended (excl header)
    bank_row = 1 + item_count
    gst_row = bank_row + 1
    gross_row = bank_row + 2
    remark_row = bank_row + 3

    data.append([sbibankdetail, '', 'Basic Total', quote.totalcylindercost, sig, '', 'Basic Total', '',
                 quote.totalmaterialcost])
    data.append(
        ['', '', f'Gst @{quote.cylinder_gst} %', round(quote.cylindergst, 2), '', '', f'Gst @{quote.material_gst} %',
         '', round(quote.materialgst, 2)])
    data.append(['', '', Paragraph('<font size=8>Cylinder<br/>Gross Total</font>', styleN),
                 Paragraph(f'<font size=9>{round(quote.grosscylindercost, 2)}</font>', styleN),
                 '', '', 'Material Gross Total', '', round(quote.grossmaterialcost, 2)])
    data.append([Paragraph(f"<font size=7>Remark: {quote.remark or ' '}</font>", styleN),
                 '', '', '', '', '', '', '', ''])

    tstyle = TableStyle([
        ('GRID', (0, 0), (8, remark_row), 0.25, colors.gray),
        ('BACKGROUND', (0, 0), (8, 0), (0.9, 0.9, 0.9)),
        ('ALIGN', (0, 0), (8, remark_row), 'CENTER'),
        ('VALIGN', (0, 0), (8, remark_row), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (8, remark_row), 8),
        ('SPAN', (0, bank_row), (1, gross_row)),  # bank paragraph
        ('SPAN', (4, bank_row), (5, gross_row)),  # signature
        ('SPAN', (6, bank_row), (7, bank_row)),
        ('SPAN', (6, gst_row), (7, gst_row)),
        ('SPAN', (6, gross_row), (7, gross_row)),
        ('SPAN', (0, remark_row), (8, remark_row)),  # remark full width
        ('BOX', (0, bank_row), (1, gross_row), 2, colors.black),
    ])

    t = Table(data, colWidths=[15, 170, 55, 60, 50, 45, 50, 50, 55])
    t.setStyle(tstyle)
    story.append(t)
    story.append(Spacer(0, 8))

    # ── Summary table ─────────────────────────────────────────────────────────
    summrydata = [
        ['Quotation Summary'],
        ['Design Charges', round(quote.designcost, 2)],
        ['Cylinder Cost', round(quote.grosscylindercost, 2)],
        ['Material Cost', round(quote.grossmaterialcost, 2)],
        ['Total Amount', round(quote.totalquotationcost, 2)],
        ['Amount In Word', Paragraph(f'<font size=8>{quote.amountinword}</font>', styleN)],
    ]
    summrytable = Table(summrydata, colWidths=[150, 400])
    summrytable.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.25, colors.gray),
        ('BACKGROUND', (0, 0), (0, 0), (0.9, 0.9, 0.9)),
        ('SPAN', (0, 0), (1, 0)),
    ]))
    story.append(summrytable)
    story.append(Spacer(0, 8))

    # ── Terms & Conditions ────────────────────────────────────────────────────
    termslist = [['Terms & Conditions']]
    for term in quote.quote_term.all():
        termslist.append([term])
    for term in quote.additionalterms.all():
        termslist.append([term.term])

    termstable = Table(termslist, colWidths=[550])
    termstable.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.25, colors.gray),
        ('BACKGROUND', (0, 0), (0, 0), (0.9, 0.9, 0.9)),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
    ]))
    story.append(termstable)

    # ── Build ─────────────────────────────────────────────────────────────────
    doc.title = f'Quote-{quote.id} - {quote.partyname} - {quote.createdby}'
    doc.build(story, canvasmaker=NumberedCanvas)  # ← NumberedCanvas handles page X of Y

    buffer.seek(0)
    return FileResponse(
        buffer,
        as_attachment=True,
        filename=f'Quote-{quote.id} - {quote.partyname} - {quote.createdby}.pdf',
    )


@login_required(login_url='/login/')
@accessview
def letterheadquotepdf(_, id):
    quote = get_object_or_404(Quotation, id=id)
    buffer = io.BytesIO()

    styles = getSampleStyleSheet()
    styleN = styles['BodyText']
    styleN.leading = 11

    # ── Header callback — called once per page automatically ──────────────────
    def draw_header(canvas, doc):
        canvas.saveState()

        # Divider below letterhead
        canvas.setFillColor(black);
        canvas.setStrokeColor(black)
        _drawpath(canvas, [MARGIN_L, H - 190], [(W - MARGIN_R, H - 190)])

        # ── Customer block (drawn as canvas text, always at same Y) ──────────
        canvas.setFont('arial', 9);
        canvas.setFillColorRGB(0.1, 0.1, 0.1)
        y = H - 160
        canvas.drawString(MARGIN_L, y, f'Customer : {quote.partyname.upper()}')
        canvas.drawRightString(W - MARGIN_R, y, f'Date : {quote.quotedate.strftime("%d/%m/%Y")}')
        canvas.drawRightString(W - MARGIN_R, y - 13, f'Quote No : {quote.id or "-"}')
        canvas.drawString(MARGIN_L, y - 13, f'Address  : {quote.add or "-"}')
        canvas.drawString(MARGIN_L, y - 26, f'Contact  : {quote.contact or "-"}')
        canvas.restoreState()

    # ── Footer callback ───────────────────────────────────────────────────────
    def draw_footer(canvas, doc):
        # Page number is handled by NumberedCanvas._draw_page_number()
        # Add anything static here — e.g. company tagline, confidentiality note
        canvas.saveState()
        canvas.setFont('arial', 7)
        canvas.setFillColorRGB(0.5, 0.5, 0.5)
        canvas.drawCentredString(W / 2, 8, 'H F Flex Pvt. Ltd. | Confidential')
        canvas.restoreState()

    def on_page(canvas, doc):
        draw_header(canvas, doc)
        draw_footer(canvas, doc)

    # ── Document + frame ──────────────────────────────────────────────────────
    frame = Frame(FRAME_X, FRAME_Y, FRAME_W, FRAME_H, id='body', showBoundary=False)
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        pageTemplates=[PageTemplate(id='main', frames=[frame], onPage=on_page)],
        leftMargin=MARGIN_L,
        rightMargin=MARGIN_R,
        topMargin=HEADER_H,
        bottomMargin=FOOTER_H,
    )

    # ── Story (all flowable content) ──────────────────────────────────────────
    story = []

    # ── Item table ────────────────────────────────────────────────────────────
    tabelheader = [
        '#',
        Paragraph('Description', styleN),
        Paragraph('Cylinder<br/>Detail', styleN),
        Paragraph('Cylinder<br/>Cost', styleN),
        Paragraph('Material<br/>Rate', styleN),
        Paragraph('Pouch<br/>Per<br/>Kg.', styleN),
        Paragraph('Per Pouch<br/>Cost.', styleN),
        Paragraph('MOQ', styleN),
        Paragraph('Material<br/>Cost', styleN),
    ]
    data = [tabelheader]

    for i, item in enumerate(quote.quotationitems.all(), 1):
        itemdesc = (
            f'{item.jobname}<br/>Size:- {item.dimension}<br/>'
            f'{item.structure}<br/>Supply :- {item.supply}'
        )
        para = Paragraph(f'<font name=arial size=8>{itemdesc}</font>', styleN)

        if item.cyl_rate and item.no_of_cyl:
            cyl_detail = Paragraph(f'<font size=8>Rs.{round(item.cyl_rate)} x {item.no_of_cyl}Nos.</font>', styleN)
            cyl_cost = Paragraph(f'<font size=8>Rs.{round(item.item_cylinder_cost, 0)}</font>', styleN)
        else:
            cyl_detail = Paragraph('<font size=8>-</font>', styleN)
            cyl_cost = Paragraph('<font size=8>-</font>', styleN)

        mat_rate = (
            Paragraph(f'<font size=8>Rs.{round(item.material_rate, 1)}</font>', styleN)
            if item.material_rate else Paragraph('<font size=8>-</font>', styleN)
        )

        data.append([
            str(i), para, cyl_detail, cyl_cost, mat_rate,
            Paragraph(f'<font size=8>{item.pouch_per_kg or "-"}</font>', styleN),
            Paragraph(f'<font size=8>Rs. {item.per_pouch_cost or "-"}</font>', styleN),
            Paragraph(f'<font size=8>{item.moq} {item.unit}</font>', styleN),
            Paragraph(f'<font size=8>Rs.{round(item.itemtotalcost)}</font>', styleN),
        ])

    # ── Footer rows ───────────────────────────────────────────────────────────
    sbibank = (
        '<font size=8>Bank Name:- State bank of India<br/>'
        'Branch:- VITA<br/>'
        'Account Name:- H F FLEX PVT. LTD.<br/>'
        'Account No:- 38244070864<br/>'
        'IFS Code:- SBIN0000285</font>'
        '<br/><font name="LohitDevanagari" size=8>'
        'कोटेशन में दीए हुए बैंक अकाउंट के अलावा कीसी और बैंक अकाउंट पर पेमेंट ना करें।'
        '</font>'
    )
    sbibankdetail = Paragraph(sbibank, styleN)

    item_count = len(data) - 1  # items already appended (excl header)
    bank_row = 1 + item_count
    gst_row = bank_row + 1
    gross_row = bank_row + 2
    remark_row = bank_row + 3

    data.append(
        [sbibankdetail, '', 'Basic Total', quote.totalcylindercost, "", '', 'Basic Total', '', quote.totalmaterialcost])
    data.append(
        ['', '', f'Gst @{quote.cylinder_gst} %', round(quote.cylindergst, 2), '', '', f'Gst @{quote.material_gst} %',
         '', round(quote.materialgst, 2)])
    data.append(['', '', Paragraph('<font size=8>Cylinder<br/>Gross Total</font>', styleN),
                 Paragraph(f'<font size=9>{round(quote.grosscylindercost, 2)}</font>', styleN),
                 '', '', 'Material Gross Total', '', round(quote.grossmaterialcost, 2)])
    data.append([Paragraph(f"<font size=7>Remark: {quote.remark or ' '}</font>", styleN),
                 '', '', '', '', '', '', '', ''])

    tstyle = TableStyle([
        ('GRID', (0, 0), (8, remark_row), 0.25, colors.gray),
        ('BACKGROUND', (0, 0), (8, 0), (0.9, 0.9, 0.9)),
        ('ALIGN', (0, 0), (8, remark_row), 'CENTER'),
        ('VALIGN', (0, 0), (8, remark_row), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (8, remark_row), 8),
        ('SPAN', (0, bank_row), (1, gross_row)),  # bank paragraph
        ('SPAN', (4, bank_row), (5, gross_row)),  # signature
        ('SPAN', (6, bank_row), (7, bank_row)),
        ('SPAN', (6, gst_row), (7, gst_row)),
        ('SPAN', (6, gross_row), (7, gross_row)),
        ('SPAN', (0, remark_row), (8, remark_row)),  # remark full width
        ('BOX', (0, bank_row), (1, gross_row), 2, colors.black),
    ])

    t = Table(data, colWidths=[15, 170, 55, 60, 50, 45, 50, 50, 55])
    t.setStyle(tstyle)
    story.append(t)
    story.append(Spacer(0, 8))

    # ── Summary table ─────────────────────────────────────────────────────────
    summrydata = [
        ['Quotation Summary'],
        ['Design Charges', round(quote.designcost, 2)],
        ['Cylinder Cost', round(quote.grosscylindercost, 2)],
        ['Material Cost', round(quote.grossmaterialcost, 2)],
        ['Total Amount', round(quote.totalquotationcost, 2)],
        ['Amount In Word', Paragraph(f'<font size=8>{quote.amountinword}</font>', styleN)],
    ]
    summrytable = Table(summrydata, colWidths=[150, 400])
    summrytable.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.25, colors.gray),
        ('BACKGROUND', (0, 0), (0, 0), (0.9, 0.9, 0.9)),
        ('SPAN', (0, 0), (1, 0)),
    ]))
    story.append(summrytable)
    story.append(Spacer(0, 8))

    # ── Terms & Conditions ────────────────────────────────────────────────────
    termslist = [['Terms & Conditions']]
    for term in quote.quote_term.all():
        termslist.append([term])
    for term in quote.additionalterms.all():
        termslist.append([term.term])

    termstable = Table(termslist, colWidths=[550])
    termstable.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.25, colors.gray),
        ('BACKGROUND', (0, 0), (0, 0), (0.9, 0.9, 0.9)),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
    ]))
    story.append(termstable)

    # ── Build ─────────────────────────────────────────────────────────────────
    doc.title = f'Quote-{quote.id} - {quote.partyname} - {quote.createdby}'
    doc.build(story, canvasmaker=NumberedCanvas)  # ← NumberedCanvas handles page X of Y

    buffer.seek(0)
    return FileResponse(
        buffer,
        as_attachment=True,
        filename=f'Quote-{quote.id} - {quote.partyname} - {quote.createdby}.pdf',
    )
