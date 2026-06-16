import os

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from reportlab.platypus.frames import Frame as RLFrame
from myproject.access import accessview
from .models import Quotation, QuotationItem
from django.http import FileResponse
from reportlab.pdfgen import canvas
import io
from reportlab.lib.units import mm, inch
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import orange, yellow, red, black, grey
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics

from reportlab.pdfbase.ttfonts import TTFont
import reportlab.rl_config
from reportlab.platypus import Table, TableStyle, Frame, Paragraph, KeepTogether, Image, SimpleDocTemplate, PageBreak, \
    Spacer, BaseDocTemplate, PageTemplate

from reportlab.lib.styles import getSampleStyleSheet
from django.conf import settings

reportlab.rl_config.warnOnMissingFontGlyphs = 0

pdfmetrics.registerFont(TTFont('times', "times.ttf"))
pdfmetrics.registerFont(TTFont('arial', "Arial.ttf"))
pdfmetrics.registerFont(TTFont('timesbd', "timesbd.ttf"))

font_path = os.path.join(settings.BASE_DIR, "static/fonts/Lohit-Devanagari.ttf")

pdfmetrics.registerFont(TTFont('LohitDevanagari', font_path))

from reportlab.pdfgen.canvas import Canvas as PdfCanvas


class NumberedCanvas(PdfCanvas):
    def __init__(self, *args, **kwargs):
        PdfCanvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            PdfCanvas.showPage(self)
        PdfCanvas.save(self)

    def draw_page_number(self, page_count):
        # Page number
        self.setFont("arial", 9)
        self.setFillColorRGB(0.3, 0.3, 0.3)
        self.drawRightString(A4[0] - 35, 20, f'Page {self._pageNumber} of {page_count}')

        # "Continued on next page" at bottom of every page except last
        if self._pageNumber < page_count:
            self.setFont("arial", 9)
            self.setFillColorRGB(0.4, 0.4, 0.4)
            self.setLineWidth(0.5)
            self.setStrokeColorRGB(0.7, 0.7, 0.7)
            self.line(15, 45, A4[0] - 35, 45)
            self.drawCentredString(A4[0] / 2, 33, "Continued on next page...")

        # Reset colors
        self.setFillColor(black)
        self.setStrokeColor(black)


def drawpath(canvas, startpoint, nodes):
    cpath = canvas.beginPath()
    cpath.moveTo(*startpoint)
    for node in nodes:
        cpath.lineTo(*node)
    canvas.drawPath(cpath, stroke=1, fill=1)


@login_required(login_url='/login/')
@accessview
def quotepdf(_, id):
    quote = get_object_or_404(Quotation, id=id)
    buffer = io.BytesIO()

    styles = getSampleStyleSheet()
    styleN = styles["BodyText"]
    styleN.leading = 11

    def draw_letterhead(canvas, doc):
        canvas.saveState()
        p = canvas

        # --- Side strips (left triangles) ---
        p.setLineWidth(1)
        p.setStrokeColor(yellow)
        p.setFillColor(yellow)
        drawpath(p, (0, A4[1]), ((80, A4[1]), (0, A4[1] - 80)))
        p.setFillColor(orange)
        p.setStrokeColor(orange)
        drawpath(p, (0, A4[1] - 0), ((73, A4[1] - 0), (0, A4[1] - 73)))

        # --- Right green strip ---
        p.setFillColorRGB(0.7, 0.9, 0)
        p.setStrokeColorRGB(0.7, 0.9, 0)
        drawpath(p, [A4[0] - 30, A4[1]], [(A4[0], A4[1]), (A4[0], 0), (A4[0] - 30, 0)])

        # --- Repeating "H F FLEX" text on right strip ---
        p.rotate(90)
        p.setFont("times", 14)
        p.setFillColorRGB(0.1, 0.4, 0.6)
        HF = "   H F FLEX  "
        p.drawCentredString(450, -580, HF * 10)
        p.rotate(-90)

        # --- Quotation info (top right) ---
        p.setFont("arial", 10)
        p.setFillColorRGB(0.0, 0.2, 0.5)
        p.drawRightString(A4[0] - 180, A4[1] - 30, 'Quotation No:- ')
        p.setFont("arial", 16)
        p.drawString(A4[0] - 180, A4[1] - 30, f'# {((6 - len(str(quote.id))) * "0") + str(quote.id)}')
        p.setFont("arial", 10)
        p.drawRightString(A4[0] - 180, A4[1] - 45, 'Date:- ')
        p.drawString(A4[0] - 180, A4[1] - 45, quote.quotedate.strftime("%d/%m/%Y"))
        p.drawRightString(A4[0] - 180, A4[1] - 60, 'Create By:- ')
        p.drawString(A4[0] - 180, A4[1] - 60, f'{quote.createdby} ({quote.createdby.profile.mobile})')
        p.drawRightString(A4[0] - 180, A4[1] - 75, 'Company GST:-')
        p.drawString(A4[0] - 180, A4[1] - 75, "27AADCH3462K1ZF")
        p.drawRightString(A4[0] - 180, A4[1] - 90, 'Company CIN:-')
        p.drawString(A4[0] - 180, A4[1] - 90, "U74900PN2014PTC150332")

        # --- Company name & address (top center) ---
        p.setFillColorRGB(0.1, 0.1, 0.1)
        p.setFont("timesbd", 25)
        p.drawCentredString(A4[0] / 2 - 99, A4[1] - 33.5, "H F Flex Pvt. Ltd.")
        p.setFillColorRGB(0.80, 0, 0)
        p.drawCentredString(A4[0] / 2 - 100, A4[1] - 34, "H F Flex Pvt. Ltd.")
        p.setFillColorRGB(0, 0.2, 0.5)
        p.setFont("arial", 9)
        p.drawCentredString(A4[0] / 2 - 100, A4[1] - 45, "25, Lucky Lark Textile Park, Gardi, Vita")
        p.drawCentredString(A4[0] / 2 - 100, A4[1] - 57, "Tal- Khanapur, Dist- Sangli, Maharashtra-415311")
        p.drawCentredString(A4[0] / 2 - 100, A4[1] - 70, f"Contact:- {quote.createdby.profile.mobile}")
        p.drawCentredString(A4[0] / 2 - 100, A4[1] - 84, " Email:- hfflexpvtltd@gmail.com, Website: www.hfflex.co.in")

        # --- Divider line ---
        p.setFillColor(black)
        p.setStrokeColor(black)
        drawpath(p, [5, A4[1] - 105], [(A4[0] - 35, A4[1] - 105)])

        canvas.restoreState()

    # Frame: leaves room for header (top) and page number (bottom)
    frame = RLFrame(15, 40, 550, A4[1] - 150, id='main', showBoundary=False)

    page_template = PageTemplate(
        id='letterhead',
        frames=[frame],
        onPage=draw_letterhead,
    )

    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        pageTemplates=[page_template],
        leftMargin=15,
        rightMargin=35,
        topMargin=120,
        bottomMargin=40,
    )

    # ── Build story ──────────────────────────────────────────────

    story = []

    # Customer info
    customertable = Table([
        [Paragraph(f'Customer:- {quote.partyname.upper()}', styleN)],
        [Paragraph(f'Address:- {quote.add or "-"}', styleN)],
        [Paragraph(f'Contact:- {quote.contact or "-"}', styleN)],
    ])
    story.append(customertable)
    story.append(Spacer(0, 6))

    # Table header row
    tabelheader = [
        "#",
        Paragraph("Description", styleN),
        Paragraph("Cylinder<br/>Detail", styleN),
        Paragraph("Cylinder<br/>Cost", styleN),
        Paragraph("Material<br/>Rate", styleN),
        Paragraph("Pouch<br/>Per<br/>Kg.", styleN),
        Paragraph("Per Pouch<br/>Cost.", styleN),
        Paragraph("MOQ", styleN),
        Paragraph("Material<br/>Cost", styleN),
    ]

    data = [tabelheader]

    for i, item in enumerate(quote.quotationitems.all(), 1):
        itemdesc = f'{item.jobname}<br/>Size:- {item.dimension}<br/>{item.structure}<br/>Supply :- {item.supply}'
        para = Paragraph(f'<font name=arial size=8>{itemdesc}</font>', styleN)

        if item.cyl_rate and item.no_of_cyl:
            cyl_detail = Paragraph(f'<font size=8>Rs.{round(item.cyl_rate)} x {item.no_of_cyl}Nos.</font>', styleN)
            cyl_cost = Paragraph(f'<font size=8>Rs.{round(item.item_cylinder_cost, 0)}</font>', styleN)
        else:
            cyl_detail = Paragraph('<font size=8>-</font>', styleN)
            cyl_cost = Paragraph('<font size=8>-</font>', styleN)

        mat_rate = (
            Paragraph(f'<font size=8>Rs.{round(item.material_rate, 1)}</font>', styleN)
            if item.material_rate
            else Paragraph('<font size=8>-</font>', styleN)
        )

        data.append([
            str(i),
            para,
            cyl_detail,
            cyl_cost,
            mat_rate,
            Paragraph(f'<font size=8>{item.pouch_per_kg or "-"}</font>', styleN),
            Paragraph(f'<font size=8>Rs. {item.per_pouch_cost or "-"}</font>', styleN),
            Paragraph(f'<font size=8>{item.moq} {item.unit}</font>', styleN),
            Paragraph(f'<font size=8>Rs.{round(item.itemtotalcost)}</font>', styleN),
        ])

    # ── Absolute row indices for footer rows ─────────────────────
    # header = row 0, then one row per item, then 4 footer rows
    item_count = len(quote.quotationitems.all())
    bank_row = 1 + item_count  # "Bank Detail / Basic Total" row
    gst_row = bank_row + 1  # GST row
    gross_row = bank_row + 2  # Gross Total row
    remark_row = bank_row + 3  # Remark row (full-width)

    # ── Bank detail paragraph ────────────────────────────────────
    sbibank = """<font size=8>Bank Name:- State bank of India<br/>
                    Branch:- VITA,<br/>
                    Current Account Name- H F FLEX PVT. LTD.<br/>
                    Bank Account No:-38244070864<br/>
                    BANK IFS CODE: SBIN0000285<br/></font>
                    <font name="LohitDevanagari" size=8>कोटेशन में दीए हुए बैंक अकाउंट के अलावा कीसी और बैंक अकाउंट पर पेमेंट ना करें।
                    </font>"""
    sbibankdetail = Paragraph(sbibank, styleN)

    if quote.approvedby.username == "khadimhusen":
        sig = Image("static/images/husensign.png", 1.2 * inch, 1.2 * inch)
    else:
        sig = Image("static/images/firojsign.png", 1.2 * inch, 1.2 * inch)

    # ── Footer rows — every row must have exactly 9 cells ────────
    data.append([
        sbibankdetail, "",  # col 0-1: bank paragraph (spans down)
        "Basic Total", quote.totalcylindercost,  # col 2-3
        sig, "",  # col 4-5: signature (spans down)
        "Basic Total", "",  # col 6-7
        quote.totalmaterialcost,  # col 8
    ])
    data.append([
        "", "",  # col 0-1: covered by span
        f'Gst @{quote.cylinder_gst} %', round(quote.cylindergst, 2),
        "", "",  # col 4-5: covered by span
        f'Gst @{quote.material_gst} %', "",
        round(quote.materialgst, 2),
    ])
    data.append([
        "", "",  # col 0-1: covered by span
        Paragraph('<font size=8>Cylinder<br/>Gross Total</font>', styleN),
        Paragraph(f'<font size=9>{round(quote.grosscylindercost, 2)}</font>', styleN),
        "", "",  # col 4-5: covered by span
        "Material Gross Total", "",
        round(quote.grossmaterialcost, 2),
    ])
    data.append([
        Paragraph(f"<font size=7>Remark: {quote.remark or ' '}</font>", styleN),
        "", "", "", "", "", "", "", "",
    ])

    # ── Table style using absolute row indices ────────────────────
    tstyle = TableStyle([
        ("GRID", (0, 0), (8, remark_row), 0.25, colors.gray),
        ('BACKGROUND', (0, 0), (8, 0), (0.9, 0.9, 0.9)),
        ("ALIGN", (0, 0), (8, remark_row), "CENTER"),
        ("VALIGN", (0, 0), (8, remark_row), "MIDDLE"),
        ("FONTSIZE", (0, 0), (8, remark_row), 8),

        # Bank label (col 0-1) spans all 3 data rows
        ('SPAN', (0, bank_row), (1, gross_row)),

        # Signature (col 4-5) spans all 3 data rows
        ('SPAN', (4, bank_row), (5, gross_row)),

        # Col 6-7 merged per row (label columns)
        ('SPAN', (6, bank_row), (7, bank_row)),
        ('SPAN', (6, gst_row), (7, gst_row)),
        ('SPAN', (6, gross_row), (7, gross_row)),

        # Remark spans full width
        ('SPAN', (0, remark_row), (8, remark_row)),

        # Thicker border around bank detail block
        ("BOX", (0, bank_row), (1, gross_row), 2, colors.black),
    ])

    t = Table(data, colWidths=[15, 170, 55, 60, 50, 45, 50, 50, 55])
    t.setStyle(tstyle)
    story.append(t)
    story.append(Spacer(0, 8))

    # ── Summary table ─────────────────────────────────────────────
    summrydata = [
        ["Quotation Summary"],
        ["Design Charges", round(quote.designcost, 2)],
        ["Cylinder Cost", round(quote.grosscylindercost, 2)],
        ["Material Cost", round(quote.grossmaterialcost, 2)],
        ["Total Amount", round(quote.totalquotationcost, 2)],
        ["Amount In Word", Paragraph(f'<font size=8>{quote.amountinword}</font>', styleN)],
    ]
    summrytable = Table(summrydata, colWidths=[150, 400])
    summrytable.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.gray),
        ('BACKGROUND', (0, 0), (0, 0), (0.9, 0.9, 0.9)),
        ('SPAN', (0, 0), (1, 0)),
    ]))
    story.append(summrytable)
    story.append(Spacer(0, 8))

    # ── Terms & Conditions ────────────────────────────────────────
    termslist = [["Terms & Conditions"]]
    for term in quote.quote_term.all():
        termslist.append([term])
    for term in quote.additionalterms.all():
        termslist.append([term.term])

    termstable = Table(termslist, colWidths=[550])
    termstable.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.gray),
        ('BACKGROUND', (0, 0), (0, 0), (0.9, 0.9, 0.9)),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    story.append(termstable)

    # ── Build & return ────────────────────────────────────────────
    doc.title = f"Quote-{quote.id} - {quote.partyname} - {quote.createdby}"
    doc.build(story, canvasmaker=NumberedCanvas)

    buffer.seek(0)
    return FileResponse(
        buffer,
        as_attachment=True,
        filename=f"Quote-{quote.id} - {quote.partyname} - {quote.createdby}.pdf",
    )

@login_required(login_url='/login/')
@accessview
def letterheadquotepdf(_, id):
    quote = get_object_or_404(Quotation, id=id)
    buffer = io.BytesIO()

    styles = getSampleStyleSheet()
    styleN = styles["BodyText"]
    styleN.leading = 11

    def draw_letterhead(canvas, doc):
        canvas.saveState()
        p = canvas

        # --- Divider line ---
        p.setFillColor(grey)
        p.setStrokeColor(grey)
        drawpath(p, [15, A4[1] - 140], [(A4[0] - 30, A4[1] - 140)])

        canvas.restoreState()

    # Frame: leaves room for header (top) and page number (bottom)
    frame = RLFrame(15, 30, 550, A4[1] - 170, id='main', showBoundary=False)

    page_template = PageTemplate(
        id='letterhead',
        frames=[frame],
        onPage=draw_letterhead,
    )

    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        pageTemplates=[page_template],
        leftMargin=15,
        rightMargin=35,
        topMargin=120,
        bottomMargin=40,
    )

    # ── Build story ──────────────────────────────────────────────

    story = []

    # Customer info
    customertable = Table([
        [Paragraph(f'Customer:- {quote.partyname.upper()}', styleN)],
        [Paragraph(f'Address:- {quote.add or "-"}', styleN)],
        [Paragraph(f'Contact:- {quote.contact or "-"}', styleN)],
    ])
    story.append(customertable)
    story.append(Spacer(0, 6))

    # Table header row
    tabelheader = [
        "#",
        Paragraph("Description", styleN),
        Paragraph("Cylinder<br/>Detail", styleN),
        Paragraph("Cylinder<br/>Cost", styleN),
        Paragraph("Material<br/>Rate", styleN),
        Paragraph("Pouch<br/>Per<br/>Kg.", styleN),
        Paragraph("Per Pouch<br/>Cost.", styleN),
        Paragraph("MOQ", styleN),
        Paragraph("Material<br/>Cost", styleN),
    ]

    data = [tabelheader]

    for i, item in enumerate(quote.quotationitems.all(), 1):
        itemdesc = f'{item.jobname}<br/>Size:- {item.dimension}<br/>{item.structure}<br/>Supply :- {item.supply}'
        para = Paragraph(f'<font name=arial size=8>{itemdesc}</font>', styleN)

        if item.cyl_rate and item.no_of_cyl:
            cyl_detail = Paragraph(f'<font size=8>Rs.{round(item.cyl_rate)} x {item.no_of_cyl}Nos.</font>', styleN)
            cyl_cost = Paragraph(f'<font size=8>Rs.{round(item.item_cylinder_cost, 0)}</font>', styleN)
        else:
            cyl_detail = Paragraph('<font size=8>-</font>', styleN)
            cyl_cost = Paragraph('<font size=8>-</font>', styleN)

        mat_rate = (
            Paragraph(f'<font size=8>Rs.{round(item.material_rate, 1)}</font>', styleN)
            if item.material_rate
            else Paragraph('<font size=8>-</font>', styleN)
        )

        data.append([
            str(i),
            para,
            cyl_detail,
            cyl_cost,
            mat_rate,
            Paragraph(f'<font size=8>{item.pouch_per_kg or "-"}</font>', styleN),
            Paragraph(f'<font size=8>Rs. {item.per_pouch_cost or "-"}</font>', styleN),
            Paragraph(f'<font size=8>{item.moq} {item.unit}</font>', styleN),
            Paragraph(f'<font size=8>Rs.{round(item.itemtotalcost)}</font>', styleN),
        ])

    # ── Absolute row indices for footer rows ─────────────────────
    # header = row 0, then one row per item, then 4 footer rows
    item_count = len(quote.quotationitems.all())
    bank_row = 1 + item_count  # "Bank Detail / Basic Total" row
    gst_row = bank_row + 1  # GST row
    gross_row = bank_row + 2  # Gross Total row
    remark_row = bank_row + 3  # Remark row (full-width)

    # ── Bank detail paragraph ────────────────────────────────────
    sbibank = """<font size=8>Bank Name:- State bank of India<br/>
                    Branch:- VITA,<br/>
                    Current Account Name- H F FLEX PVT. LTD.<br/>
                    Bank Account No:-38244070864<br/>
                    BANK IFS CODE: SBIN0000285<br/></font>
                    <font name="LohitDevanagari" size=8>कोटेशन में दीए हुए बैंक अकाउंट के अलावा कीसी और बैंक अकाउंट पर पेमेंट ना करें।
                    </font>"""
    sbibankdetail = Paragraph(sbibank, styleN)

    if quote.approvedby.username == "khadimhusen":
        sig = Image("static/images/husensign.png", 1.2 * inch, 1.2 * inch)
    else:
        sig = Image("static/images/firojsign.png", 1.2 * inch, 1.2 * inch)

    # ── Footer rows — every row must have exactly 9 cells ────────
    data.append([
        sbibankdetail, "",  # col 0-1: bank paragraph (spans down)
        "Basic Total", quote.totalcylindercost,  # col 2-3
        sig, "",  # col 4-5: signature (spans down)
        "Basic Total", "",  # col 6-7
        quote.totalmaterialcost,  # col 8
    ])
    data.append([
        "", "",  # col 0-1: covered by span
        f'Gst @{quote.cylinder_gst} %', round(quote.cylindergst, 2),
        "", "",  # col 4-5: covered by span
        f'Gst @{quote.material_gst} %', "",
        round(quote.materialgst, 2),
    ])
    data.append([
        "", "",  # col 0-1: covered by span
        Paragraph('<font size=8>Cylinder<br/>Gross Total</font>', styleN),
        Paragraph(f'<font size=9>{round(quote.grosscylindercost, 2)}</font>', styleN),
        "", "",  # col 4-5: covered by span
        "Material Gross Total", "",
        round(quote.grossmaterialcost, 2),
    ])
    data.append([
        Paragraph(f"<font size=7>Remark: {quote.remark or ' '}</font>", styleN),
        "", "", "", "", "", "", "", "",
    ])

    # ── Table style using absolute row indices ────────────────────
    tstyle = TableStyle([
        ("GRID", (0, 0), (8, remark_row), 0.25, colors.gray),
        ('BACKGROUND', (0, 0), (8, 0), (0.9, 0.9, 0.9)),
        ("ALIGN", (0, 0), (8, remark_row), "CENTER"),
        ("VALIGN", (0, 0), (8, remark_row), "MIDDLE"),
        ("FONTSIZE", (0, 0), (8, remark_row), 8),

        # Bank label (col 0-1) spans all 3 data rows
        ('SPAN', (0, bank_row), (1, gross_row)),

        # Signature (col 4-5) spans all 3 data rows
        ('SPAN', (4, bank_row), (5, gross_row)),

        # Col 6-7 merged per row (label columns)
        ('SPAN', (6, bank_row), (7, bank_row)),
        ('SPAN', (6, gst_row), (7, gst_row)),
        ('SPAN', (6, gross_row), (7, gross_row)),

        # Remark spans full width
        ('SPAN', (0, remark_row), (8, remark_row)),

        # Thicker border around bank detail block
        ("BOX", (0, bank_row), (1, gross_row), 2, colors.black),
    ])

    t = Table(data, colWidths=[15, 170, 55, 60, 50, 45, 50, 50, 55])
    t.setStyle(tstyle)
    story.append(t)
    story.append(Spacer(0, 8))

    # ── Summary table ─────────────────────────────────────────────
    summrydata = [
        ["Quotation Summary"],
        ["Design Charges", round(quote.designcost, 2)],
        ["Cylinder Cost", round(quote.grosscylindercost, 2)],
        ["Material Cost", round(quote.grossmaterialcost, 2)],
        ["Total Amount", round(quote.totalquotationcost, 2)],
        ["Amount In Word", Paragraph(f'<font size=8>{quote.amountinword}</font>', styleN)],
    ]
    summrytable = Table(summrydata, colWidths=[150, 400])
    summrytable.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.gray),
        ('BACKGROUND', (0, 0), (0, 0), (0.9, 0.9, 0.9)),
        ('SPAN', (0, 0), (1, 0)),
    ]))
    story.append(summrytable)
    story.append(Spacer(0, 8))

    # ── Terms & Conditions ────────────────────────────────────────
    termslist = [["Terms & Conditions"]]
    for term in quote.quote_term.all():
        termslist.append([term])
    for term in quote.additionalterms.all():
        termslist.append([term.term])

    termstable = Table(termslist, colWidths=[550])
    termstable.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.gray),
        ('BACKGROUND', (0, 0), (0, 0), (0.9, 0.9, 0.9)),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))
    story.append(termstable)

    # ── Build & return ────────────────────────────────────────────
    doc.title = f"Quote-{quote.id} - {quote.partyname} - {quote.createdby}"
    doc.build(story, canvasmaker=NumberedCanvas)

    buffer.seek(0)
    return FileResponse(
        buffer,
        as_attachment=True,
        filename=f"Quote-{quote.id} - {quote.partyname} - {quote.createdby}.pdf",
    )

@login_required(login_url='/login/')
@accessview
def letterheadquotepdf1(_, id):
    quote = get_object_or_404(Quotation, id=id)
    buffer = io.BytesIO()

    p = canvas.Canvas(buffer, pagesize=A4, bottomup=1)

    styles = getSampleStyleSheet()
    styleN = styles["BodyText"]
    styleN.leading = 11

    # ── Customer table (reused on every page) ────────────────────
    customertable = Table([
        [
            Paragraph(f'Customer:- {quote.partyname.upper()}', styleN),
            Paragraph(f'Quote No:- # {((6 - len(str(quote.id))) * "0") + str(quote.id)}', styleN),
        ],
        [
            Paragraph(f'Address:- {quote.add or "-"}', styleN),
            f'Date:- {quote.created.strftime("%d/%m/%Y")}',
        ],
        [
            Paragraph(f'Contact:- {quote.contact or "-"}', styleN),
            f'Created By :- {quote.createdby}',
        ],
    ], colWidths=[400, 150])

    # ── Table header ─────────────────────────────────────────────
    tabelheader = [
        "#",
        Paragraph("Description", styleN),
        Paragraph("Cylinder<br/>Detail", styleN),
        Paragraph("Cylinder<br/>Cost", styleN),
        Paragraph("Material<br/>Rate", styleN),
        Paragraph("Pouch<br/>Per<br/>Kg.", styleN),
        Paragraph("Per Pouch<br/>Cost.", styleN),
        Paragraph("MOQ", styleN),
        Paragraph("Material<br/>Cost", styleN),
    ]

    base_tstyle = TableStyle([
        ("GRID",       (0, 0), (-1, -1), 0.25, colors.gray),
        ('BACKGROUND', (0, 0), (-1,  0), (0.9, 0.9, 0.9)),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
    ])

    def flush_page(data, is_last=False):
        """Render current data rows to the canvas frame and call showPage."""
        if not is_last:
            p.setFont("arial", 9)
            p.setFillColorRGB(0.4, 0.4, 0.4)
            p.setStrokeColorRGB(0.7, 0.7, 0.7)
            p.setLineWidth(0.5)
            p.line(15, 45, A4[0] - 35, 45)
            p.drawCentredString(A4[0] / 2, 33, "Continued on next page...")
            p.setFillColorRGB(0, 0, 0)

        t = Table(data, colWidths=[15, 170, 55, 60, 50, 45, 50, 50, 55])
        t.setStyle(base_tstyle)
        frame = Frame(15, 30, 550, A4[1] - 190, showBoundary=False)
        frame.addFromList([customertable, t], p)
        if not is_last:
            p.showPage()

    # ── Build item rows with page-break logic ────────────────────
    data        = [tabelheader]
    pageheight  = 67 * mm
    item_number = 1

    for item in quote.quotationitems.all():
        itemdesc = (
            f'{item.jobname}<br/>Size:- {item.dimension}<br/>'
            f'{item.structure}<br/>Supply :- {item.supply}'
        )
        para = Paragraph(f'<font name=arial size=8>{itemdesc}</font>', styleN)
        para.wrapOn(p, 165, 0)
        pageheight += para.height

        if item.cyl_rate and item.no_of_cyl:
            cyl_detail = Paragraph(f'<font size=8>Rs.{round(item.cyl_rate)} x {item.no_of_cyl}Nos.</font>', styleN)
            cyl_cost   = Paragraph(f'<font size=8>Rs.{round(item.item_cylinder_cost, 0)}</font>', styleN)
        else:
            cyl_detail = Paragraph('<font size=8>-</font>', styleN)
            cyl_cost   = Paragraph('<font size=8>-</font>', styleN)

        mat_rate = (
            Paragraph(f'<font size=8>Rs.{round(item.material_rate, 1)}</font>', styleN)
            if item.material_rate
            else Paragraph('<font size=8>-</font>', styleN)
        )

        row = [
            str(item_number),
            para,
            cyl_detail,
            cyl_cost,
            mat_rate,
            Paragraph(f'<font size=8>{item.pouch_per_kg or "-"}</font>', styleN),
            Paragraph(f'<font size=8>Rs. {item.per_pouch_cost or "-"}</font>', styleN),
            Paragraph(f'<font size=8>{item.moq} {item.unit}</font>', styleN),
            Paragraph(f'<font size=8>Rs.{round(item.itemtotalcost)}</font>', styleN),
        ]
        item_number += 1

        if pageheight / mm >= 190:
            # Flush current page without this row, then start fresh
            flush_page(data, is_last=False)
            data       = [tabelheader, row]
            pageheight = 67 * mm + para.height
        else:
            data.append(row)

    # ── Footer rows (bank detail, GST, gross total, remark) ──────
    # IMPORTANT: sbibankdetail must be in bank_row col-0 (anchor cell of span)
    sbibank = """<font size=8>Bank Name:- State bank of India<br/>
Branch:- VITA,<br/>
Current Account Name- H F FLEX PVT. LTD.<br/>
Bank Account No:-38244070864<br/>
BANK IFS CODE: SBIN0000285</font>"""
    sbibankdetail = Paragraph(sbibank, styleN)

    if quote.approvedby.username == "khadimhusen":
        sig = Image("static/images/husensign.png", 1.2 * inch, 1.2 * inch)
    else:
        sig = Image("static/images/firojsign.png", 1.2 * inch, 1.2 * inch)

    # Absolute row indices
    item_count = len(data) - 1          # rows already in data (excluding header)
    bank_row   = 1 + item_count         # = len(data) after append
    gst_row    = bank_row + 1
    gross_row  = bank_row + 2
    remark_row = bank_row + 3

    # Every row has exactly 9 cells
    data.append([
        sbibankdetail, "",              # col 0-1 — anchor cell for bank span
        "Basic Total", quote.totalcylindercost,
        sig, "",                        # col 4-5 — anchor cell for sig span
        "Basic Total", "",
        quote.totalmaterialcost,
    ])
    data.append([
        "", "",                         # covered by bank span
        f'Gst @{quote.cylinder_gst} %', round(quote.cylindergst, 2),
        "", "",                         # covered by sig span
        f'Gst @{quote.material_gst} %', "",
        round(quote.materialgst, 2),
    ])
    data.append([
        "", "",                         # covered by bank span
        Paragraph('<font size=8>Cylinder<br/>Gross Total</font>', styleN),
        Paragraph(f'<font size=9>{round(quote.grosscylindercost, 2)}</font>', styleN),
        "", "",                         # covered by sig span
        "Material Gross Total", "",
        round(quote.grossmaterialcost, 2),
    ])
    data.append([
        Paragraph(f"<font size=7>Remark: {quote.remark or ' '}</font>", styleN),
        "", "", "", "", "", "", "", "",  # 8 padding cells
    ])

    tstyle = TableStyle([
        ("GRID",       (0, 0),          (8, remark_row),   0.25, colors.gray),
        ('BACKGROUND', (0, 0),          (8, 0),            (0.9, 0.9, 0.9)),
        ("ALIGN",      (0, 0),          (8, remark_row),   "CENTER"),
        ("VALIGN",     (0, 0),          (8, remark_row),   "MIDDLE"),
        ("FONTSIZE",   (0, 0),          (8, remark_row),   8),

        # Bank paragraph spans cols 0-1, all 3 data rows
        ('SPAN', (0, bank_row),   (1, gross_row)),
        # Signature spans cols 4-5, all 3 data rows
        ('SPAN', (4, bank_row),   (5, gross_row)),
        # Label columns 6-7 merged per row
        ('SPAN', (6, bank_row),   (7, bank_row)),
        ('SPAN', (6, gst_row),    (7, gst_row)),
        ('SPAN', (6, gross_row),  (7, gross_row)),
        # Remark full width
        ('SPAN', (0, remark_row), (8, remark_row)),
        # Thick border around bank block
        ('BOX',  (0, bank_row),   (1, gross_row),  2, colors.black),
    ])

    t = Table(data, colWidths=[15, 170, 55, 60, 50, 45, 50, 50, 55])
    t.setStyle(tstyle)

    # ── Summary table ─────────────────────────────────────────────
    summrydata = [
        ["Quotation Summary"],
        ["Design Charges",  round(quote.designcost, 2)],
        ["Cylinder Cost",   round(quote.grosscylindercost, 2)],
        ["Material Cost",   round(quote.grossmaterialcost, 2)],
        ["Total Amount",    round(quote.totalquotationcost, 2)],
        ["Amount In Word",  Paragraph(f'<font size=8>{quote.amountinword}</font>', styleN)],
    ]
    summrytable = Table(summrydata, colWidths=[150, 400])
    summrytable.setStyle(TableStyle([
        ("GRID",       (0, 0), (-1, -1), 0.25, colors.gray),
        ('BACKGROUND', (0, 0), (0,  0),  (0.9, 0.9, 0.9)),
        ('SPAN',       (0, 0), (1,  0)),
    ]))

    # ── Terms & Conditions ────────────────────────────────────────
    termslist = [["Terms & Conditions"]]
    for term in quote.quote_term.all():
        termslist.append([term])
    for term in quote.additionalterms.all():
        termslist.append([term.term])

    termstable = Table(termslist, colWidths=[550])
    termstable.setStyle(TableStyle([
        ("GRID",       (0, 0), (-1, -1), 0.25, colors.gray),
        ('BACKGROUND', (0, 0), (0,  0),  (0.9, 0.9, 0.9)),
        ("FONTSIZE",   (0, 0), (-1, -1), 7),
    ]))

    # ── Final frame — flush remaining content page by page ───────
    # Use a story list and keep splitting across pages so nothing is dropped
    story = [customertable, t, Spacer(0, 5), summrytable, Spacer(0, 5), termstable]

    frame = Frame(15, 30, 550, A4[1] - 190, showBoundary=False)
    while story:
        frame.addFromList(story, p)
        if story:
            # Content left over — start a new page
            p.setFont("arial", 9)
            p.setFillColorRGB(0.4, 0.4, 0.4)
            p.setStrokeColorRGB(0.7, 0.7, 0.7)
            p.setLineWidth(0.5)
            p.line(15, 45, A4[0] - 35, 45)
            p.drawCentredString(A4[0] / 2, 33, "Continued on next page...")
            p.setFillColorRGB(0, 0, 0)
            p.showPage()
            frame = Frame(15, 30, 550, A4[1] - 190, showBoundary=False)

    p.setTitle(f"Quote-{quote.id} - {quote.partyname} - {quote.createdby}")
    p.save()
    buffer.seek(0)

    return FileResponse(
        buffer,
        as_attachment=True,
        filename=f"Quote-{quote.id} - {quote.partyname} - {quote.createdby}.pdf",
    )