from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from myproject.access import accessview
from .models import Po
from django.http import FileResponse
from reportlab.pdfgen import canvas
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import orange, yellow
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics

from reportlab.pdfbase.ttfonts import TTFont
import reportlab.rl_config
from reportlab.platypus import Table, TableStyle, Frame, Paragraph, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet

reportlab.rl_config.warnOnMissingFontGlyphs = 0

pdfmetrics.registerFont(TTFont('times', "times.ttf"))
pdfmetrics.registerFont(TTFont('arial', "Arial.ttf"))
pdfmetrics.registerFont(TTFont('timesbd', "timesbd.ttf"))


def drawpath(canvas, startpoint, nodes):
    cpath = canvas.beginPath()
    cpath.moveTo(*startpoint)
    for node in nodes:
        cpath.lineTo(*node)
    canvas.drawPath(cpath, stroke=1, fill=1)


def join_parts(*parts, sep='-'):
    """Joins non-empty, stripped parts with sep — without ever doubling it
    when a part already ends with one. Real address data occasionally has
    a trailing separator typed into the field itself (e.g. addname
    'OFFICE-'), and the old code's naive f'{a}-{b}' concatenation produced
    a visible 'OFFICE--B-142...' double-dash in that case."""
    cleaned = [str(p).strip().rstrip(sep).strip() for p in parts if p not in (None, '')]
    cleaned = [p for p in cleaned if p]
    return sep.join(cleaned)


def draw_string_fit(canvas_obj, x, y, text, font, size, max_width):
    """drawString, but truncated with an ellipsis if it would run past
    max_width — the supplier/delivery header block lays two columns of
    free-text (addresses, names, contact info) side by side with no
    wrapping at all; a long enough value in the left column (a real
    supplier address, not a synthetic one) visibly overlaps the right
    column's text on the same row otherwise."""
    canvas_obj.setFont(font, size)
    if canvas_obj.stringWidth(text, font, size) <= max_width:
        canvas_obj.drawString(x, y, text)
        return
    ellipsis = '...'
    ellipsis_width = canvas_obj.stringWidth(ellipsis, font, size)
    truncated = text
    while truncated and canvas_obj.stringWidth(truncated, font, size) + ellipsis_width > max_width:
        truncated = truncated[:-1]
    canvas_obj.drawString(x, y, truncated + ellipsis)


@login_required(login_url='/login/')
@accessview
def popdf(request, id):
    purchase = get_object_or_404(Po, id=id)
    buffer = io.BytesIO()

    p = canvas.Canvas(buffer, pagesize=A4, bottomup=1)
    p.setLineWidth(1)
    p.setStrokeColor(yellow)
    p.setFillColor(yellow)

    drawpath(p, (0, A4[1]), [(80, A4[1]), (0, A4[1] - 80)])
    p.setFillColor(orange)
    p.setStrokeColor(orange)
    drawpath(p, (0, A4[1] - 0), ((73, A4[1] - 0), (0, A4[1] - 73)))

    drawpath(p, [10, A4[1] - 100], [(10, A4[1] - 180)])
    drawpath(p, [315, A4[1] - 100], [(315, A4[1] - 180)])
    drawpath(p, [5, A4[1] - 190], [(A4[0] - 5, A4[1] - 190)])
    drawpath(p, [5, A4[1] - 90], [(A4[0] - 5, A4[1] - 90)])

    p.setFillColorRGB(0.7, 0.9, 0)
    p.setStrokeColorRGB(0.7, 0.9, 0)
    drawpath(p, [A4[0] - 20, A4[1]], [(A4[0], A4[1]), (A4[0], 0), (A4[0] - 20, 0)])

    p.rotate(90)
    p.setFont("times", 14)
    p.setFillColorRGB(0.1, 0.4, 0.6)
    HF = "   H F FLEX  "
    p.drawCentredString(450, -590, HF * 12)
    p.rotate(-90)
    p.setFont("arial", 10)
    p.setFillColorRGB(0.0, 0.2, 0.5)
    p.drawRightString(A4[0] - 170, A4[1] - 20, 'Purchase Order No:- ')
    p.setFont("arial", 16)
    p.drawString(A4[0] - 170, A4[1] - 20, f'# {((6 - len(str(purchase.id))) * "0") + str(purchase.id)}')




    hyperlinkwidth=canvas_obj.stringWidth(f'# {((6 - len(str(purchase.id))) * "0") + str(purchase.id)}',"arial", 16)
    p.linkURL(url=f'https://www.hfflex.com/purchase/purchasedetail/{str(purchase.id)}/',
                           rect=(A4[0] - 170, A4[1] - 22,A4[0] - 170+hyperlinkwidth, A4[1] - 22+16),
                           relative=0)







    p.setFont("arial", 10)
    p.drawRightString(A4[0] - 170, A4[1] - 35, 'Date:- ')

    p.drawString(A4[0] - 170, A4[1] - 35, purchase.created.strftime("%d/%m/%Y"))
    p.drawRightString(A4[0] - 170, A4[1] - 50, 'Expteced Delivery:- ')
    p.drawString(A4[0] - 170, A4[1] - 50, purchase.delivery_date.strftime("%d/%m/%Y"))
    p.drawRightString(A4[0] - 170, A4[1] - 65, 'Transport:- ')
    p.drawString(A4[0] - 170, A4[1] - 65, purchase.transport)
    p.drawRightString(A4[0] - 170, A4[1] - 80, 'Payment Terms:- ')
    p.drawString(A4[0] - 170, A4[1] - 80, str(purchase.payment_terms or ""))
    p.setFillColorRGB(0.95, 0.95, 0.95)
    p.setFont("timesbd", 25)
    p.drawCentredString(A4[0] / 2 - 98, A4[1] - 25, "H F Flex Pvt. Ltd.")
    p.setFillColorRGB(0.80, 0, 0)
    p.drawCentredString(A4[0] / 2 - 100, A4[1] - 28, "H F Flex Pvt. Ltd.")
    p.setFillColorRGB(0, 0.2, 0.5)
    p.setFont("arial", 9)
    p.drawCentredString(A4[0] / 2 - 100, A4[1] - 42,
                        "25, Lucky Lark Textile Park, Gardi, Vita")
    p.drawCentredString(A4[0] / 2 - 100, A4[1] - 55, "Tal- Khanapur, Dist- Sangli, Maharashtra-415311")
    p.drawCentredString(A4[0] / 2 - 100, A4[1] - 68, "Contact:- 8552827683, 9765643576,")
    p.drawCentredString(A4[0] / 2 - 100, A4[1] - 81, " Email:- hfflexpvtltd@gmail.com, Website: www.hfflex.co.in")
    p.drawString(20, A4[1] - 105, 'Purchase Order To:-')
    p.drawString(325, A4[1] - 105, 'Delivery To:-')
    p.setFillColorRGB(0.80, 0, 0)
    p.setFont("arial", 12)
    p.drawString(20, A4[1] - 118, f'{purchase.supplier}')
    p.drawString(325, A4[1] - 118, 'H F FLEX PVT. LTD.')

    p.setFont("arial", 9)
    p.setFillColorRGB(0.0, 0.2, 0.4)

    item = purchase.supplier.addresses.first()
    if item:
        p.drawString(20, A4[1] - 130, f'{item.addname or ""}-{item.add1 or ""}')
        p.drawString(20, A4[1] - 143, f'{item.add2 or ""}-{item.pincode or ""}')
    if purchase.supplier.gst:
        p.drawString(20, A4[1] - 156, f'Gst:- {purchase.supplier.gst or ""}')
    person = purchase.supplier.persons.first()
    if person:
        p.drawString(20, A4[1] - 169, f'Contact Person: -{person.name or ""} - {person.mobile or ""}')
    else:
        p.drawString(20, A4[1] - 169, "Contact Person: -")

    p.drawString(20, A4[1] - 182, f'Email: - {purchase.supplier.email or ""}')
    p.drawString(325, A4[1] - 130, f'{purchase.delivery_at.addname or ""}-{purchase.delivery_at.add1 or ""}')
    p.drawString(325, A4[1] - 143, f'{purchase.delivery_at.add2 or ""}-{purchase.delivery_at.pincode or ""}')
    p.drawString(325, A4[1] - 156, 'Gst:- 27AADCH3462K1ZF')
    p.drawString(325, A4[1] - 169,
                 f'Contact Person: -{purchase.createdby.profile.prefix or ""} {purchase.createdby.get_full_name() or ""}-{purchase.createdby.profile.mobile or ""}')
    p.drawString(325, A4[1] - 182, 'Email: -hfflexpvtltd@gmail.com')

    flow_obj = []
    styles = getSampleStyleSheet()

    styleN = styles["BodyText"]

    data = [["#", "Description", "Category", "Qty.", "Price", "Unit", "Total"]]
    i = 1
    for item in purchase.poitem.all():
        datalist = []
        datalist.append(str(i))
        i = i + 1
        itemdesc = "<br/>".join(item.description.split("\n"))
        datalist.append(Paragraph(f'<font size=7>{itemdesc}</font>', styleN))
        datalist.append(item.category)
        datalist.append(item.qty)
        datalist.append(round(item.rate, 2))
        datalist.append(item.unit)
        datalist.append(item.total)
        data.append(datalist)
    else:
        terms = ""
        for term in purchase.poterm.all():
            terms = terms + term.term + "<br />"

    styleN.leading = 9
    termsandcondition = Paragraph(f'<font  size=8>{terms}</font>', styleN)

    data.append(["", "Terms & Conditions", "Total Qty", purchase.totalqty, "SubTotal", "", f'Rs. {purchase.pototal}'])
    data.append([termsandcondition, "", "", "", f'CGST {purchase.tax1} %', "", f'Rs. {purchase.cgst}'])
    data.append(["", "", "", "", f'SGST {purchase.tax2} %', "", f'Rs. {purchase.sgst}'])
    data.append([Paragraph(f' {purchase.inword}', styleN), "", "", "", "Grand Total", "", f'Rs. {purchase.grosstotal}'])
    data.append(
        [Paragraph(f' <font color=red><b>Remark:-</b> {purchase.remark or ""}</font>', styleN), "", "", "", "", "", ""])
    data.append([f"Created by {purchase.createdby} On {purchase.created.strftime('%d-%m-%Y')}",
                 "", "",
                 f"Approved by {purchase.approvedby or ''} On {purchase.approve_date.strftime('%d-%m-%Y') if purchase.approve_date else ''}",
                 "", "", ""])

    tstyle = TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.gray),
                         ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                         ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                         ("FONTSIZE", (0, 0), (-1, -1), 8),

                         ('SPAN', (0, -1), (2, -1)),
                         ('SPAN', (3, -1), (6, -1)),

                         ('SPAN', (0, -2), (6, -2)),
                         ('SPAN', (0, -3), (3, -3)),
                         ('SPAN', (-3, -3), (-2, -3)),
                         ('SPAN', (-3, -4), (-2, -4)),
                         ('SPAN', (4, -5), (5, -5)),
                         ('SPAN', (0, -4), (3, -5)),
                         ('SPAN', (-3, -6), (-2, -6)),

                         ])

    t = Table(data, colWidths=[15, 275, 60, 50, 48, 28, 80])

    t.setStyle(tstyle)
    flow_obj.append(t)

    frame1 = Frame(20, 50, 550, A4[1] - 250, showBoundary=False)
    frame1.addFromList(flow_obj, p)

    if not purchase.approvedby:
        p.setFillColorRGB(0.80, 0, 0, 0.4)
        p.setFont("arial", 30)
        p.drawCentredString(A4[0] / 2, 20, "Pending for Approval")
    else:
        p.setFillColorRGB(0, 0.8, 0, 0.4)
        p.setFont("arial", 30)
        p.drawCentredString(A4[0] / 2, 20, "Approved")

    p.setFillColorRGB(0.90, 0, 0, 1)
    p.setFont("arial", 8)
    p.drawCentredString(A4[0] / 2, 7, "Note:-Please Don't Print This Unless Extremely Necessary")
    p.setTitle(f"Po-{purchase.id}")
    p.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f'{purchase.id} - {purchase.supplier}.pdf')


def build_po_pdf_buffer(purchase):
    """Renders the same Purchase Order PDF as the old newpopdf view, minus
    the request/response plumbing — extracted so the new DRF API (see
    purchase.api_viewsets.PoViewSet.pdf) can reuse the exact same layout
    instead of reimplementing it."""
    buffer = io.BytesIO()
    pagestartposition = 250
    p = canvas.Canvas(buffer, pagesize=A4, bottomup=1)
    page = 1

    #CREATE HEADER ON TOP OF EVERY PAGE
    def pageheader():
        nonlocal page

        p.setLineWidth(1)
        p.setStrokeColor(yellow)
        p.setFillColor(yellow)

        drawpath(p, (0, A4[1]), [(80, A4[1]), (0, A4[1] - 80)])
        p.setFillColor(orange)
        p.setStrokeColor(orange)
        drawpath(p, (0, A4[1] - 0), [(73, A4[1] - 0), (0, A4[1] - 73)])


        drawpath(p, [10, A4[1] - 90], [(A4[0] - 30, A4[1] - 90)])

        p.setFillColorRGB(0.7, 0.9, 0)
        p.setStrokeColorRGB(0.7, 0.9, 0)
        drawpath(p, [A4[0] - 20, A4[1]], [(A4[0], A4[1]), (A4[0], 0), (A4[0] - 20, 0)])

        p.rotate(90)
        p.setFont("times", 14)
        p.setFillColorRGB(0.1, 0.4, 0.6)
        HF = "   H F FLEX  "
        p.drawCentredString(450, -590, HF * 12)
        p.rotate(-90)
        p.setFont("arial", 10)
        p.setFillColorRGB(0.0, 0.2, 0.5)
        p.drawRightString(A4[0] - 170, A4[1] - 20, 'Purchase Order No:- ')
        p.setFont("arial", 16)
        p.drawString(A4[0] - 170, A4[1] - 20, f'# {((6 - len(str(purchase.id))) * "0") + str(purchase.id)}')

        hyperlinkwidth=p.stringWidth(f'# {((6 - len(str(purchase.id))) * "0") + str(purchase.id)}',"arial", 16)
        p.linkURL(url=f'https://www.hfflex.com/purchase/purchasedetail/{str(purchase.id)}/',
                           rect=(A4[0] - 170, A4[1] - 22,A4[0] - 170+hyperlinkwidth, A4[1] - 22+16),
                           relative=0)




        p.setFont("arial", 10)
        p.drawRightString(A4[0] - 170, A4[1] - 35, 'Date:- ')

        p.drawString(A4[0] - 170, A4[1] - 35, purchase.created.strftime("%d/%m/%Y"))
        p.drawRightString(A4[0] - 170, A4[1] - 50, 'Expteced Delivery:- ')
        p.drawString(A4[0] - 170, A4[1] - 50, purchase.delivery_date.strftime("%d/%m/%Y"))
        p.drawRightString(A4[0] - 170, A4[1] - 65, 'Transport:- ')
        p.drawString(A4[0] - 170, A4[1] - 65, purchase.transport)
        p.drawRightString(A4[0] - 170, A4[1] - 80, 'Payment Terms:- ')
        p.drawString(A4[0] - 170, A4[1] - 80, str(purchase.payment_terms or ""))
        p.setFillColorRGB(0.95, 0.95, 0.95)
        p.setFont("timesbd", 25)
        p.drawCentredString(A4[0] / 2 - 98, A4[1] - 25, "H F Flex Pvt. Ltd.")
        p.setFillColorRGB(0.80, 0, 0)
        p.drawCentredString(A4[0] / 2 - 100, A4[1] - 28, "H F Flex Pvt. Ltd.")
        p.setFillColorRGB(0, 0.2, 0.5)
        p.setFont("arial", 9)
        p.drawCentredString(A4[0] / 2 - 100, A4[1] - 42,
                            "25, Lucky Lark Textile Park, Gardi, Vita")
        p.drawCentredString(A4[0] / 2 - 100, A4[1] - 55, "Tal- Khanapur, Dist- Sangli, Maharashtra-415311")
        p.drawCentredString(A4[0] / 2 - 100, A4[1] - 68, "Contact:- 8552827683, 9765643576,")
        p.drawCentredString(A4[0] / 2 - 100, A4[1] - 81, " Email:- hfflexpvtltd@gmail.com, Website: www.hfflex.co.in")
        p.drawString(500, 20, f'Page({page})')
        page = page + 1
        p.setFillColorRGB(0.90, 0, 0, 1)
        p.setFont("arial", 8)
        p.drawCentredString(A4[0] / 2, 7, "Note:-Please Don't Print This Unless Extremely Necessary")

    frame1 = Frame(20, 50, 550, A4[1] - pagestartposition , showBoundary=False)
    pageheader()

    # SUPPLIER DETAIL for first page

    p.setFillColor(orange)
    p.setStrokeColor(orange)
    drawpath(p, [10, A4[1] - 100], [(10, A4[1] - 180)])
    drawpath(p, [315, A4[1] - 100], [(315, A4[1] - 180)])
    drawpath(p, [10, A4[1] - 190], [(A4[0] - 30, A4[1] - 190)])
    # Column widths for draw_string_fit — divider lines sit at x=315 (left
    # column: x=20..315) and the page's right margin (right column:
    # x=325..A4[0]-30); a few points of margin are subtracted from each so
    # truncated text never quite touches the divider/edge.
    LEFT_COL_WIDTH = 315 - 20 - 5
    RIGHT_COL_WIDTH = (A4[0] - 30) - 325 - 5

    p.setFillColorRGB(0.0, 0.2, 0.4)
    p.drawString(20, A4[1] - 105, 'Purchase Order To:-')
    p.drawString(325, A4[1] - 105, 'Delivery To:-')
    p.setFillColorRGB(0.8, 0, 0)
    draw_string_fit(p, 20, A4[1] - 118, f'{purchase.supplier}', "arial", 12, LEFT_COL_WIDTH)
    draw_string_fit(p, 325, A4[1] - 118, f'{purchase.ship_to}', "arial", 12, RIGHT_COL_WIDTH)

    p.setFillColorRGB(0.0, 0.2, 0.4)

    item = purchase.supplier.addresses.first()
    if item:
        draw_string_fit(p, 20, A4[1] - 130, join_parts(item.addname, item.add1), "arial", 9, LEFT_COL_WIDTH)
        draw_string_fit(p, 20, A4[1] - 143, join_parts(item.add2, item.pincode), "arial", 9, LEFT_COL_WIDTH)
    if purchase.supplier.gst:
        draw_string_fit(p, 20, A4[1] - 156, f'Gst:- {purchase.supplier.gst or ""}', "arial", 9, LEFT_COL_WIDTH)
    person = purchase.supplier.persons.first()
    contact_line = f'Contact Person: -{join_parts(person.name, person.mobile, sep=" - ")}' if person else 'Contact Person: -'
    draw_string_fit(p, 20, A4[1] - 169, contact_line, "arial", 9, LEFT_COL_WIDTH)

    draw_string_fit(p, 20, A4[1] - 182, f'Email: - {purchase.supplier.email or ""}', "arial", 9, LEFT_COL_WIDTH)
    draw_string_fit(
        p, 325, A4[1] - 130, join_parts(purchase.delivery_at.addname, purchase.delivery_at.add1),
        "arial", 9, RIGHT_COL_WIDTH,
    )
    draw_string_fit(
        p, 325, A4[1] - 143, join_parts(purchase.delivery_at.add2, purchase.delivery_at.pincode),
        "arial", 9, RIGHT_COL_WIDTH,
    )
    draw_string_fit(p, 325, A4[1] - 156, f'{purchase.ship_to.gst or ""}', "arial", 9, RIGHT_COL_WIDTH)

    if purchase.ship_to.name == "H F FLEX PRIVATE LIMITED":
        full_name = join_parts(purchase.createdby.profile.prefix, purchase.createdby.get_full_name(), sep=' ')
        draw_string_fit(
            p, 325, A4[1] - 169, f'Contact Person: -{join_parts(full_name, purchase.createdby.profile.mobile)}',
            "arial", 9, RIGHT_COL_WIDTH,
        )
        draw_string_fit(p, 325, A4[1] - 182, f'Email:- {purchase.createdby.email or ""}', "arial", 9, RIGHT_COL_WIDTH)
    else:
        # purchase.ship_to.persons.first() can be None — a customer with no
        # contact person on file — which previously crashed this branch
        # with an AttributeError (confirmed live: any PO shipped to a real
        # third-party customer without a recorded contact person 500'd here).
        ship_to_person = purchase.ship_to.persons.first()
        contact_line = (
            f'Contact Person: -{join_parts(ship_to_person.name, ship_to_person.mobile, sep=" - ")}'
            if ship_to_person else 'Contact Person: -'
        )
        draw_string_fit(p, 325, A4[1] - 169, contact_line, "arial", 9, RIGHT_COL_WIDTH)
        draw_string_fit(p, 325, A4[1] - 182, f'Email:- {purchase.ship_to.email or ""}', "arial", 9, RIGHT_COL_WIDTH)

    styles = getSampleStyleSheet()
    styleN = styles["BodyText"]
    styleN.leading = 9

    COL_WIDTHS = [15, 275, 60, 50, 48, 28, 80]
    HEADER_ROW = ["#", "Description", "Category", "Qty.", "Price", "Unit", "Total"]

    def measure_height(rows, style=None):
        """Real height a Table with these rows (at our fixed column
        widths) needs, via ReportLab's own layout engine — used to decide
        what fits on a page instead of the old fixed '67mm baseline, break
        past 180mm' heuristic, which had no real connection to what was
        actually being rendered. Confirmed on a real PO with long,
        multi-line item descriptions: that heuristic broke to a new page
        after a single item despite most of the page still being empty.

        Pass `style` (a SPAN-bearing TableStyle) when measuring rows that
        will be rendered with merged cells — the footer block has a
        Paragraph in column 0 that's meant to span columns 0-3 (~400pt)
        once rendered, but measured bare (no SPAN) it gets wrapped into
        column 0's actual 15pt width instead, confirmed inflating its
        height by ~40x and making it look like it never fits."""
        t = Table(rows, colWidths=COL_WIDTHS)
        if style:
            t.setStyle(TableStyle(style))
        return t.wrap(sum(COL_WIDTHS), 0)[1]

    def flush_table(table, frame):
        """frame.addFromList() silently leaves a flowable in the list (and
        therefore never draws it) if it doesn't fit — its own docstring
        claims it 'raises an exception', but the actual implementation
        just breaks out of its loop instead. Confirmed directly: an
        oversized table rendered a page with nothing on it at all, no
        error. Surface that loudly instead of shipping a silently
        incomplete Purchase Order document."""
        remaining = [table]
        frame.addFromList(remaining, p)
        if remaining:
            raise RuntimeError(
                f'Purchase Order #{purchase.id} PDF: a table did not fit on its page '
                f'(likely an unusually long item description) and would have been silently dropped.'
            )

    header_height = measure_height([HEADER_ROW])

    terms = ""
    for term in purchase.poterm.all():
        terms = terms + term.term + "<br />"
    termsandcondition = Paragraph(f'<font  size=8>{terms}</font>', styleN)

    # The footer/summary block (6 rows) is one atomic unit — it has merged
    # cells spanning across rows (Terms & Conditions, the amount-in-words
    # line, ...) that only make sense together, so it's placed as a single
    # item in the same page-fitting loop as the PO items below, never
    # split partway across a page boundary.
    footer_rows = [
        ["", "Terms & Conditions", "Total Qty", purchase.totalqty, "SubTotal", "", f'Rs. {purchase.pototal}'],
        [termsandcondition, "", "", "", f'CGST {purchase.tax1} %', "", f'Rs. {purchase.cgst}'],
        ["", "", "", "", f'SGST {purchase.tax2} %', "", f'Rs. {purchase.sgst}'],
        [Paragraph(f' {purchase.inword}', styleN), "", "", "", "Grand Total", "", f'Rs. {purchase.grosstotal}'],
        [
            Paragraph(f' <font color=red><b>Remark:-</b> {purchase.remark or ""}</font>', styleN),
            "", "", "", "", "", "",
        ],
        [
            f"Created by {purchase.createdby} On {purchase.created.strftime('%d-%m-%Y')}", "", "",
            f"Approved by {purchase.approvedby or ''} On "
            f"{purchase.approve_date.strftime('%d-%m-%Y') if purchase.approve_date else ''}",
            "", "", "",
        ],
    ]

    # ROUNDEDCORNERS rounds the table's own outer corners (top row's top
    # corners, bottom row's bottom corners) while leaving the internal
    # GRID lines between cells sharp/straight — just the outer silhouette.
    TABLE_CORNER_RADIUS = 6
    FOOTER_STYLE = [("GRID", (0, 0), (-1, -1), 0.25, colors.gray),
                     ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                     ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                     ("FONTSIZE", (0, 0), (-1, -1), 8),
                     ("ROUNDEDCORNERS", [TABLE_CORNER_RADIUS] * 4),
                     ('SPAN', (0, -1), (2, -1)),
                     ('SPAN', (3, -1), (6, -1)),
                     ('SPAN', (0, -2), (6, -2)),
                     ('SPAN', (0, -3), (3, -3)),
                     ('SPAN', (-3, -3), (-2, -3)),
                     ('SPAN', (-3, -4), (-2, -4)),
                     ('SPAN', (4, -5), (5, -5)),
                     ('SPAN', (0, -4), (3, -5)),
                     ('SPAN', (-3, -6), (-2, -6)),
                     ]
    CONTINUED_STYLE = [("GRID", (0, 0), (-1, -1), 0.25, colors.gray),
                        ('BACKGROUND', (0, 0), (-1, 0), (0.9, 0.9, 0.9)),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("ROUNDEDCORNERS", [TABLE_CORNER_RADIUS] * 4),
                        ]

    # Real available height for item rows on each page, matching the Frame
    # heights actually used below (250pt reserved above the frame on page
    # 1 for the logo/supplier block, 150pt on later pages for just the
    # banner), less a small bottom-margin cushion.
    FIRST_PAGE_HEIGHT = (A4[1] - 250) - 50
    LATER_PAGE_HEIGHT = (A4[1] - 150) - 50

    page_capacity = FIRST_PAGE_HEIGHT - header_height
    data = [HEADER_ROW]
    pageheight = 0

    def start_new_page(next_row):
        """Flush the current page's accumulated rows (never including
        next_row — that's what didn't fit) and begin a fresh one, primed
        with next_row as its first content row."""
        nonlocal pagestartposition, frame1, page_capacity, pageheight, data
        pagestartposition = 150
        p.setFont("arial", 20)
        p.drawString(100, 100, " Page Continue ...")
        t = Table(data, colWidths=COL_WIDTHS)
        t.setStyle(TableStyle(CONTINUED_STYLE))
        flush_table(t, frame1)
        p.showPage()
        frame1 = Frame(15, 50, 550, A4[1] - pagestartposition, showBoundary=False)
        pageheader()
        page_capacity = LATER_PAGE_HEIGHT - header_height
        data = [HEADER_ROW, next_row]
        pageheight = measure_height([next_row])

    def place_row(row):
        """Calculate the row's real height, and either add it to the
        current page or start a new one for it — the same check either
        way, applied one row at a time (items, then the footer block as
        one final row) until everything's been placed."""
        nonlocal pageheight, data
        row_height = measure_height([row])
        if pageheight + row_height <= page_capacity or len(data) == 1:
            # len(data) == 1: no content rows on this page yet — always
            # accept the first one even if it alone exceeds capacity, so a
            # single very tall row can't get dropped or loop forever.
            data.append(row)
            pageheight += row_height
        else:
            start_new_page(row)

    i = 1
    for item in purchase.poitem.all().order_by('-id'):
        datalist = [str(i)]
        i = i + 1

        itemdesc = "<br/>".join(item.description.split("\n"))
        para = Paragraph(f'<font size=7>{itemdesc}</font>', styleN)
        datalist.append(para)
        datalist.append(item.category)
        datalist.append(item.qty)
        datalist.append(round(item.rate, 2))
        datalist.append(item.unit)
        datalist.append(item.total)

        place_row(datalist)

    # The footer is 6 rows glued together by SPANs that only make sense as
    # a block, so it's measured and placed as a single unit rather than
    # going through place_row() row-by-row (which would let it split
    # across a page boundary, breaking those SPANs). Measured WITH
    # FOOTER_STYLE applied — bare (unspanned), the Paragraphs meant to
    # span columns 0-3 instead wrap into column 0's actual 15pt width,
    # confirmed inflating the measured height by ~40x.
    footer_height = measure_height(footer_rows, style=FOOTER_STYLE)
    if pageheight + footer_height <= page_capacity or len(data) == 1:
        data.extend(footer_rows)
    else:
        start_new_page(footer_rows[0])
        data.extend(footer_rows[1:])

    t = Table(data, colWidths=COL_WIDTHS)
    t.setStyle(TableStyle(FOOTER_STYLE))

    frame1 = Frame(20, 50, 550, A4[1] - pagestartposition, showBoundary=False)
    flush_table(t, frame1)

    if not purchase.approvedby:
        p.setFillColorRGB(0.80, 0, 0, 0.4)
        p.setFont("arial", 30)
        p.drawCentredString(A4[0] / 2, 20, "Pending for Approval")
    else:
        p.setFillColorRGB(0, 0.8, 0, 0.4)
        p.setFont("arial", 30)
        p.drawCentredString(A4[0] / 2, 20, "Approved")


    p.setTitle(f"Po-{purchase.id}")
    p.save()
    buffer.seek(0)
    return buffer


@login_required(login_url='/login/')
@accessview
def newpopdf(request, id):
    purchase = get_object_or_404(Po, id=id)
    buffer = build_po_pdf_buffer(purchase)
    return FileResponse(buffer, as_attachment=True, filename=f'{purchase.id} - {purchase.supplier}.pdf')
