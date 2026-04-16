import os

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from myproject.access import accessview
from .models import Quotation,  QuotationItem
from django.http import FileResponse
from reportlab.pdfgen import canvas
import io
from reportlab.lib.units import mm, inch
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import orange, yellow,red,black
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics

from reportlab.pdfbase.ttfonts import TTFont
import reportlab.rl_config
from reportlab.platypus import Table, TableStyle, Frame, Paragraph, KeepTogether, Image, SimpleDocTemplate, PageBreak, Spacer, BaseDocTemplate, PageTemplate

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
    cpath=canvas.beginPath()
    cpath.moveTo(*startpoint)
    for node in nodes:
        cpath.lineTo(*node)
    canvas.drawPath(cpath,stroke=1,fill=1)


@login_required(login_url='/login/')
@accessview
def quotepdf(_, id):
    quote = get_object_or_404(Quotation, id=id)
    buffer = io.BytesIO()

    styles = getSampleStyleSheet()
    styleN = styles["BodyText"]
    styleN.leading = 11

    page_counter = [1]  # mutable so inner function can modify

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

        # --- Page number ---


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

    from reportlab.platypus import BaseDocTemplate, PageTemplate
    from reportlab.platypus.frames import Frame as RLFrame

    # Frame: leaves room for header (top) and page number (bottom)
    frame = RLFrame(15, 40, 550, A4[1] - 150, id='main', showBoundary=False)

    page_template = PageTemplate(
        id='letterhead',
        frames=[frame],
        onPage=draw_letterhead
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

    # Table header
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

        mat_rate = Paragraph(f'<font size=8>Rs.{round(item.material_rate, 1)}</font>', styleN) if item.material_rate else Paragraph('<font size=8>-</font>', styleN)

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

    # Bank detail + totals rows
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

    data.append(["Bank Detail", "", "Basic Total", quote.totalcylindercost, sig, "", "Basic Total", "", quote.totalmaterialcost])
    data.append([sbibankdetail, "", f'Gst @{quote.cylinder_gst} %', round(quote.cylindergst, 2), "", "", f'Gst @{quote.material_gst} %', "", round(quote.materialgst, 2)])
    data.append(["", "", Paragraph(f'<font size=8>Cylinder<br/>Gross Total</font>', styleN),
                 Paragraph(f'<font size=9>{round(quote.grosscylindercost, 2)}</font>', styleN),
                 "", "", "Material Gross Total", "", round(quote.grossmaterialcost, 2)])
    data.append([Paragraph(f"<font size=7>Remark:{quote.remark or ' '}</font>", styleN)])

    tstyle = TableStyle([
        ("GRID", (0, 0), (8, -1), 0.25, colors.gray),
        ('BACKGROUND', (0, 0), (8, 0), (0.9, 0.9, 0.9)),
        ("ALIGN", (0, 0), (8, -1), "CENTER"),
        ("VALIGN", (0, 0), (8, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (8, -1), 8),
        ('SPAN', (0, -4), (1, -4)),
        ('SPAN', (7, -4), (6, -4)),
        ('SPAN', (7, -3), (6, -3)),
        ('SPAN', (7, -2), (6, -2)),
        ('SPAN', (0, -2), (1, -3)),
        ('SPAN', (0, -1), (8, -1)),
        ('SPAN', (4, -2), (5, -4)),
        ("GRID", (0, -1), (1, -4), 2, colors.black),
    ])

    t = Table(data, colWidths=[15, 170, 55, 60, 50, 45, 50, 50, 55])
    t.setStyle(tstyle)
    story.append(t)
    story.append(Spacer(0, 8))

    # Summary table
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

    # Terms & Conditions
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

    # ── Build & return ───────────────────────────────────────────
    doc.title = f"Quote-{quote.id} - {quote.partyname} - {quote.createdby}"
    doc.build(story, canvasmaker=NumberedCanvas)

    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True,
                        filename=f"Quote-{quote.id} - {quote.partyname} - {quote.createdby}.pdf")



@login_required(login_url='/login/')
@accessview
def quotepdf1(_, id):

    quote = get_object_or_404(Quotation, id=id)
    buffer = io.BytesIO()

    p = canvas.Canvas(buffer, pagesize=A4, bottomup=1)

    page=1

    def letterheader():
        nonlocal page
        p.setLineWidth(1)
        p.setStrokeColor(yellow)
        p.setFillColor(yellow)
        drawpath(p, (0, A4[1]), ((80, A4[1]), (0, A4[1] - 80)))
        p.setFillColor(orange)
        p.setStrokeColor(orange)
        drawpath(p, (0, A4[1] - 0), ((73, A4[1] - 0), (0, A4[1] - 73)))
        p.setFillColorRGB(0.7, 0.9, 0)
        p.setStrokeColorRGB(0.7, 0.9, 0)
        drawpath(p, [A4[0] - 30, A4[1]], [(A4[0], A4[1]), (A4[0], 0), (A4[0] - 30, 0)])
        p.rotate(90)
        p.setFont("times", 14)
        p.setFillColorRGB(0.1, 0.4, 0.6)
        HF="   H F FLEX  "
        p.drawCentredString(450, -580,HF*10)
        p.rotate(-90)

        p.setFont("arial", 10)
        p.setFillColorRGB(0.0, 0.2, 0.5)
        p.drawRightString(A4[0] - 180, A4[1] - 30, 'Quotation No:- ')
        p.setFont("arial", 16)
        p.drawString(A4[0] - 180, A4[1] - 30, f'# {((6 - len(str(   quote.id))) * "0") + str(quote.id) }')
        p.setFont("arial", 10)
        p.drawRightString(A4[0] - 180, A4[1] - 45, 'Date:- ')
        p.drawString(A4[0] - 180, A4[1] - 45, quote.quotedate.strftime("%d/%m/%Y"))

        p.drawRightString(A4[0] - 180, A4[1] - 60, 'Create By:- ')
        p.drawString(A4[0] - 180, A4[1] - 60, f'{quote.createdby} ({quote.createdby.profile.mobile})' )

        p.drawRightString(A4[0] - 180, A4[1] - 75, 'Company GST:-')
        p.drawString(A4[0] - 180, A4[1] - 75, "27AADCH3462K1ZF")

        p.drawRightString(A4[0] - 180, A4[1] - 90, 'Company CIN:-')
        p.drawString(A4[0] - 180, A4[1] - 90, "U74900PN2014PTC150332")
        p.drawString(500, 20, f'Page({page})')
        page=page+1
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
        p.setFillColor(black)
        p.setStrokeColor(black)
        drawpath(p, [5, A4[1] - 105], [(A4[0] - 35, A4[1] - 105)])

    frame1 = Frame(15, 30, 550, A4[1] - 130, showBoundary=False)
    letterheader()
    p.setFillColorRGB(0.10, 0.10, 0.10)

    #
    # p.drawString(35, A4[1] - 105, f'Customer:- {quote.partyname.upper()}')
    # p.drawString(35, A4[1] - 120, f'Address:- {quote.add or "-"}')
    # p.drawString(35, A4[1] - 135, f'Contact:- {quote.contact or "-"}')
    styles = getSampleStyleSheet()
    styleN = styles["BodyText"]

    tabelheader = ["#",
                    Paragraph("Description", styleN),
                    Paragraph("Cylinder<br/>Detail", styleN),
                    Paragraph("Cylinder<br/>Cost", styleN),
                    Paragraph("Material<br/>Rate", styleN),
                    Paragraph("Pouch<br/> Per<br/>Kg.", styleN),
                    Paragraph("Per Pouch <br/> Cost.", styleN),
                    Paragraph("MOQ", styleN),
                    Paragraph("Material <br/> Cost", styleN)]

  # datatabel start from here

    customertable= Table([[Paragraph(f'Customer:- {quote.partyname.upper()}',styleN)],
                         [Paragraph(f'Address:- {quote.add or "-"}',styleN)],
                         [Paragraph(f'Contact:- {quote.contact or "-"}',styleN)]],)


    data = [tabelheader]
    i = 1
    pageheight = 67*mm
    for item in quote.quotationitems.all():

        itemdata = []
        itemdata.append(str(i))
        i = i + 1
        itemdesc=f'{item.jobname}<br/> Size:- {item.dimension}<br/>{item.structure}<br/> Supply :- {item.supply}'
        para = Paragraph(f'<font name=arial size=8 >{itemdesc}</font>', styleN)
        para.wrapOn(p, 165, 0)
        pageheight=pageheight+para.height
        itemdata.append(para)

        if item.cyl_rate and item.no_of_cyl:
            itemdata.append(Paragraph(f'<font size=8>Rs.{round(item.cyl_rate)} x {item.no_of_cyl}Nos.</font>',styleN))
            itemdata.append(Paragraph(f'<font size=8>Rs.{round(item.item_cylinder_cost,0)}</font>', styleN))
        else:
            itemdata.append(Paragraph(f'<font size=8>-</font>',styleN))
            itemdata.append(Paragraph(f'<font size=8>-</font>', styleN))

        if item.material_rate:
            itemdata.append(Paragraph(f'<font size=8>Rs.{round(item.material_rate, 1)} </font>',styleN))
        else:
            itemdata.append(Paragraph(f'<font size=8>-</font>',styleN))

        itemdata.append(Paragraph(f'<font size=8>{item.pouch_per_kg or "-"}</font>',styleN))
        itemdata.append(Paragraph(f'<font size=8>Rs. {item.per_pouch_cost or "-"}</font>',styleN))
        itemdata.append(Paragraph(f'<font size=8>{item.moq} {item.unit}</font>',styleN))
        itemdata.append(Paragraph(f'<font size=8>Rs.{round(item.itemtotalcost)}</font>',styleN))
        if pageheight/mm < 180:
            data.append(itemdata)
        else:
            # Draw a "continued" notice at the bottom of the current page
            tstyle = TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.gray),
                                 ('BACKGROUND', (0, 0), (-1, 0), (0.9, 0.9, 0.9)),
                                 ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                 ("FONTSIZE", (0, 0), (-1, -1), 8),
                                 ])

            t = Table(data, colWidths=[15, 170, 55, 60, 50, 45, 50, 50, 55])
            t.setStyle(tstyle)

            # frame1.addFromList([t,t], p)

            frame1.addFromList([customertable,t], p)

            p.showPage()
            frame1 = Frame(15, 30, 550, A4[1] - 130, showBoundary=False)
            letterheader()
            pageheight = 67 * mm
            data = [tabelheader]
            data.append(itemdata)

            para.wrapOn(p, 165, 0)
            pageheight += para.height  # re-add height for this item on new page


    else:
        styleN.leading = 11
        sbibank = """<font size=8>Bank Name:- State bank of India<br/>
                        Branch:- VITA,<br/>
                        Current Account Name- H F FLEX PVT. LTD.<br/>
                        Bank Account No:-38244070864 <br/>
                        BANK IFS CODE: SBIN0000285<br/> </font>
                        <font name="LohitDevanagari" size= 8 >कोटेशन में दीए हुए बैंक अकाउंट के अलावा कीसी और बैंक अकाउंट पर पेमेंट ना करें।
                        </font>
                       """

        sbibankdetail = Paragraph(sbibank, styleN)

        if quote.approvedby.username == "khadimhusen":
            a = Image("static/images/husensign.png", 1.2 * inch, 1.2 * inch)
        else:
            a = Image("static/images/firojsign.png", 1.2 * inch, 1.2 * inch)

        data.append(["Bank Detail", "", "Basic Total", quote.totalcylindercost, a, "", "Basic Total", "",
                     quote.totalmaterialcost])
        data.append([sbibankdetail, "", f'Gst @{quote.cylinder_gst} %', round(quote.cylindergst, 2), "", "",
                     f'Gst @{quote.material_gst} %', "", round(quote.materialgst, 2)])
        data.append(["", "", Paragraph(f'<font size=8> Cylinder<br/>Gross Total</font>', styleN),
                     Paragraph(f'<font size=9> {round(quote.grosscylindercost, 2)}</font>', styleN), "", "",
                     "Material Gross Total", "", round(quote.grossmaterialcost, 2)])

        data.append( [ Paragraph(f"<font size=7>  Remark:{quote.remark or ' '}</font> ",styleN),])

        tstyle = TableStyle([("GRID", (0, 0), (8, -1), 0.25, colors.gray),
                             ('BACKGROUND', (0, 0), (8, 0), (0.9, 0.9, 0.9)),
                             ("ALIGN", (0, 0), (8, -1), "CENTER"),
                             ("VALIGN", (0, 0), (8, -1), "MIDDLE"),
                             ("FONTSIZE", (0, 0), (8, -1), 8),
                             ('SPAN', (0, -4), (1, -4)),  # "Bankdetail"
                             ('SPAN', (7, -4), (6, -4)),  # "Material Gross Total "
                             ('SPAN', (7, -3), (6, -3)),  # "Material Total"
                             ('SPAN', (7, -2), (6, -2)),  # "Gst @18.00 % "
                             ('SPAN', (0, -2), (1, -3)),  # bankdetail
                             ('SPAN', (0, -1), (8, -1)),  # amount in word
                             ('SPAN', (4, -2), (5, -4)),  # titlebankdetail
                             ("GRID", (0, -1), (1, -4), 2, colors.black)

                             ])

        t = Table(data, colWidths=[15, 170, 55, 60, 50, 45, 50, 50, 55])
        t.setStyle(tstyle)

        summrydata = [
                        ["Quotation Summary"],
                        ["Design Charges",round(quote.designcost,2)],
                        ["Cylinder Cost", round(quote.grosscylindercost, 2)],
                        ["Material Cost",  round(quote.grossmaterialcost, 2)],
                        ["Total Amount",  round(quote.totalquotationcost, 2)],
                        ["Amount In Word ", Paragraph(f'<font size=8> {quote.amountinword}</font>',styleN)]
                    ]

        summrytablestyle = TableStyle([("GRID",(0,0),(-1,-1), 0.25, colors.gray),
                                    ('BACKGROUND', (0, 0), (0, 0), (0.9, 0.9, 0.9)),
                                    ('SPAN', (0, 0), (1, 0)),

                                   ])

        summrytable = Table(summrydata, colWidths=[150, 400])
        summrytable.setStyle(summrytablestyle)


        termslist=[["Terms & Conditions"]]

        for term in quote.quote_term.all():
            termslist.append([term])
        for term in quote.additionalterms.all():
            termslist.append([term.term])


        termstable = Table(termslist, colWidths=[550])
        terstablestyle=TableStyle([("GRID",(0,0),(-1,-1), 0.25, colors.gray),
                                   ('BACKGROUND', (0, 0), (0, 0), (0.9, 0.9, 0.9)),
                                   ("FONTSIZE", (0, 0), (8, -1), 8),
                                   ])

        termstable.setStyle(terstablestyle)
    # frame1.addFromList([t,t], p)

    # frame1.addFromList([customertable,t, Spacer(0,5),summrytable, Spacer(0,5),termstable], p)

    # Replace the final frame1.addFromList(...) with this:

    story_items = [customertable, t, Spacer(0, 5), summrytable, Spacer(0, 5), termstable]
    frame1.addFromList(story_items, p)

    while story_items:
        # Draw "continued" notice at bottom of current page BEFORE showPage
        p.setFont("arial", 9)
        p.setFillColorRGB(0.9, 0.0, 0.0)
        p.setLineWidth(0.5)
        p.setStrokeColorRGB(0.9, 0.0, 0.0)
        p.line(15, 45, A4[0] - 35, 45)
        p.drawCentredString(A4[0] / 2, 33, "Continued on next page...")
        p.setFillColorRGB(0, 0, 0)

        p.showPage()
        frame1 = Frame(15, 30, 550, A4[1] - 140, showBoundary=False)
        letterheader()

        # Draw "continued from" notice at top of new page

        frame1.addFromList(story_items, p)

    p.setTitle(f"Quote-{quote.id} - {quote.partyname} - {quote.createdby}")
    p.save()
    buffer.seek(0)

    return FileResponse(buffer, as_attachment=True,
                        filename=f"Quote-{quote.id} - {quote.partyname} - {quote.createdby}.pdf")

@login_required(login_url='/login/')
@accessview
def letterheadquotepdf(_, id):

    quote = get_object_or_404(Quotation, id=id)
    buffer = io.BytesIO()

    p = canvas.Canvas(buffer, pagesize=A4, bottomup=1)

    frame1 = Frame(15, 30, 550, A4[1] - 190, showBoundary=False)

    p.setFillColorRGB(0.10, 0.10, 0.10)

    #
    # p.drawString(35, A4[1] - 105, f'Customer:- {quote.partyname.upper()}')
    # p.drawString(35, A4[1] - 120, f'Address:- {quote.add or "-"}')
    # p.drawString(35, A4[1] - 135, f'Contact:- {quote.contact or "-"}')
    styles = getSampleStyleSheet()
    styleN = styles["BodyText"]

    tabelheader = ["#",
                    Paragraph("Description", styleN),
                    Paragraph("Cylinder<br/>Detail", styleN),
                    Paragraph("Cylinder<br/>Cost", styleN),
                    Paragraph("Material<br/>Rate", styleN),
                    Paragraph("Pouch<br/> Per<br/>Kg.", styleN),
                    Paragraph("Per Pouch <br/> Cost.", styleN),
                    Paragraph("MOQ", styleN),
                    Paragraph("Material <br/> Cost", styleN)]

  # datatabel start from here

    customertable= Table([[Paragraph(f'Customer:- {quote.partyname.upper()}',styleN),Paragraph(f' Quote No:- # {((6 - len(str(   quote.id))) * "0") + str(quote.id)}')],
                         [Paragraph(f'Address:- {quote.add or "-"}',styleN),f'Date:- {quote.created.strftime("%d/%m/%Y")}'],
                         [Paragraph(f'Contact:- {quote.contact or "-"}',styleN),f'Created By :- {quote.createdby}']
                          ], colWidths=[400,150])


    data = [tabelheader]
    i = 1
    pageheight = 67*mm
    for item in quote.quotationitems.all():
        itemdata = []
        itemdata.append(str(i))
        i = i + 1
        itemdesc=f'{item.jobname}<br/> Size:- {item.dimension}<br/>{item.structure}<br/> Supply :- {item.supply}'
        para = Paragraph(f'<font name=arial size=8 >{itemdesc}</font>', styleN)
        para.wrapOn(p, 165, 0)
        pageheight=pageheight+para.height

        itemdata.append(para)

        if item.cyl_rate and item.no_of_cyl:
            itemdata.append(Paragraph(f'<font size=8>Rs.{round(item.cyl_rate)} x {item.no_of_cyl}Nos.</font>',styleN))
            itemdata.append(Paragraph(f'<font size=8>Rs.{round(item.item_cylinder_cost,0)}</font>', styleN))
        else:
            itemdata.append(Paragraph(f'<font size=8>-</font>',styleN))
            itemdata.append(Paragraph(f'<font size=8>-</font>', styleN))

        if item.material_rate:
            itemdata.append(Paragraph(f'<font size=8>Rs.{round(item.material_rate, 1)} </font>',styleN))
        else:
            itemdata.append(Paragraph(f'<font size=8>-</font>',styleN))

        itemdata.append(Paragraph(f'<font size=8>{item.pouch_per_kg or "-"}</font>',styleN))
        itemdata.append(Paragraph(f'<font size=8>Rs. {item.per_pouch_cost or "-"}</font>',styleN))
        itemdata.append(Paragraph(f'<font size=8>{item.moq} {item.unit}</font>',styleN))
        itemdata.append(Paragraph(f'<font size=8>Rs.{round(item.itemtotalcost)}</font>',styleN))
        if pageheight/mm < 190:
            data.append(itemdata)
        else:
            # Draw a "continued" notice at the bottom of the current page
            p.setFont("arial", 9)
            p.setFillColorRGB(0.4, 0.4, 0.4)
            p.setStrokeColorRGB(0.7, 0.7, 0.7)
            p.setLineWidth(0.5)
            p.line(15, 45, A4[0] - 35, 45)  # thin separator line
            p.drawCentredString(A4[0] / 2, 33, "✦  Continued on next page...  ✦")
            p.setFillColorRGB(0, 0, 0)  # reset fill color
            tstyle = TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.gray),
                                 ('BACKGROUND', (0, 0), (-1, 0), (0.9, 0.9, 0.9)),
                                 ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                 ("FONTSIZE", (0, 0), (-1, -1), 8),
                                 ])

            t = Table(data, colWidths=[15, 170, 55, 60, 50, 45, 50, 50, 55])
            t.setStyle(tstyle)

            # frame1.addFromList([t,t], p)

            frame1.addFromList([customertable,t], p)
            p.showPage()
            frame1 = Frame(15, 30, 550, A4[1] - 190, showBoundary=False)
            pageheight = 67 * mm
            data = [tabelheader]
            data.append(itemdata)
            para.wrapOn(p, 165, 0)
            pageheight += para.height  # re-add height for this item on new page


    else:
        styleN.leading = 11
        sbibank = """<font size=8>Bank Name:- State bank of India<br/>
                        Branch:- VITA,<br/>
                        Current Account Name- H F FLEX PVT. LTD.<br/>
                        Bank Account No:-38244070864 <br/>
                        BANK IFS CODE: SBIN0000285</font>"""

        sbibankdetail = Paragraph(sbibank, styleN)


        data.append(["Bank Detail", "", "Basic Total", quote.totalcylindercost," ", "", "Basic Total", "",
                     quote.totalmaterialcost])
        data.append([sbibankdetail, "", f'Gst @{quote.cylinder_gst} %', round(quote.cylindergst, 2), "", "",
                     f'Gst @{quote.material_gst} %', "", round(quote.materialgst, 2)])
        data.append(["", "", Paragraph(f'<font size=8> Cylinder<br/>Gross Total</font>', styleN),
                     Paragraph(f'<font size=9> {round(quote.grosscylindercost, 2)}</font>', styleN), "", "",
                     "Material Gross Total", "", round(quote.grossmaterialcost, 2)])

        data.append([])

        tstyle = TableStyle([("GRID", (0, 0), (8, -1), 0.25, colors.gray),
                             ('BACKGROUND', (0, 0), (8, 0), (0.9, 0.9, 0.9)),
                             ("ALIGN", (0, 0), (8, -1), "CENTER"),
                             ("VALIGN", (0, 0), (8, -1), "MIDDLE"),
                             ("FONTSIZE", (0, 0), (8, -1), 8),

                             ('SPAN', (0, -4), (1, -4)),  # "Bankdetail"
                             ('SPAN', (7, -4), (6, -4)),  # "Material Gross Total "
                             ('SPAN', (7, -3), (6, -3)),  # "Material Total"
                             ('SPAN', (7, -2), (6, -2)),  # "Gst @18.00 % "
                             ('SPAN', (0, -2), (1, -3)),  # bankdetail
                             ('SPAN', (0, -1), (8, -1)),  # amount in word
                             ('SPAN', (4, -2), (5, -4)),  # titlebankdetail

                             ("GRID", (0, -1), (1, -4), 2, colors.black)

                             ])

        t = Table(data, colWidths=[15, 170, 55, 60, 50, 45, 50, 50, 55])
        t.setStyle(tstyle)

        summrydata = [
                        ["Quotation Summary"],
                        ["Design Charges",round(quote.designcost,2)],
                        ["Cylinder Cost", round(quote.grosscylindercost, 2)],
                        ["Material Cost",  round(quote.grossmaterialcost, 2)],
                        ["Total Amount",  round(quote.totalquotationcost, 2)],
                        [" Amount In Word " , Paragraph(f'<font size=8> {quote.amountinword}</font>',styleN)]
                    ]

        summrytablestyle = TableStyle([("GRID",(0,0),(-1,-1), 0.25, colors.gray),
                                    ('BACKGROUND', (0, 0), (0, 0), (0.9, 0.9, 0.9)),
                                    ('SPAN', (0, 0), (1, 0)),

                                   ])

        summrytable = Table(summrydata, colWidths=[150, 400])
        summrytable.setStyle(summrytablestyle)


        termslist=[["Terms & Conditions"]]

        for term in quote.quote_term.all():
            termslist.append([term])
        for term in quote.additionalterms.all():
            termslist.append([term.term])


        termstable = Table(termslist, colWidths=[550])
        terstablestyle=TableStyle([("GRID",(0,0),(-1,-1), 0.25, colors.gray),
                                   ('BACKGROUND', (0, 0), (0, 0), (0.9, 0.9, 0.9)),
                                   ("FONTSIZE", (0, 0), (8, -1), 7),
                                   ])

        termstable.setStyle(terstablestyle)
    # frame1.addFromList([t,t], p)

    frame1.addFromList([customertable,t, Spacer(0,5),summrytable, Spacer(0,5),termstable], p)



    p.setTitle(f"Quote-{quote.id} - {quote.partyname} - {quote.createdby}")
    p.save()
    buffer.seek(0)

    return FileResponse(buffer, as_attachment=True,
                        filename=f"Quote-{quote.id} - {quote.partyname} - {quote.createdby}.pdf")
