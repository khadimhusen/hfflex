from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from myproject.access import accessview
from .models import Po
from django.http import FileResponse
from reportlab.pdfgen import canvas
import io
from reportlab.lib.units import mm
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


@login_required(login_url='/login/')
@accessview
def newpopdf(request, id):
    purchase = get_object_or_404(Po, id=id)
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
    p.setFillColorRGB(0.0, 0.2, 0.4)
    p.drawString(20, A4[1] - 105, 'Purchase Order To:-')
    p.drawString(325, A4[1] - 105, 'Delivery To:-')
    p.setFont("arial", 12)
    p.setFillColorRGB(0.8, 0, 0)
    p.drawString(20, A4[1] - 118, f'{purchase.supplier}')
    p.drawString(325, A4[1] - 118, f'{purchase.ship_to}')

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
    p.drawString(325, A4[1] - 156, f'{purchase.ship_to.gst or ""}')

    if purchase.ship_to.name == "H F FLEX PRIVATE LIMITED":

        p.drawString(325, A4[1] - 169, f'Contact Person: -{purchase.createdby.profile.prefix or ""} '
                 f'{purchase.createdby.get_full_name() or ""}-{purchase.createdby.profile.mobile or ""}')
        p.drawString(325, A4[1] - 182, f'Email:- {purchase.createdby.email or ""}')
    else:
        ship_to_person = purchase.ship_to.persons.first()
        p.drawString(325, A4[1] - 169, f'Contact Person: -{ship_to_person.name or ""} - {ship_to_person.mobile or ""}')
        p.drawString(325, A4[1] - 182, f'Email:- {purchase.ship_to.email or ""}')


    flow_obj = []

    styles = getSampleStyleSheet()
    styleN = styles["BodyText"]

    data = [["#", "Description", "Category", "Qty.", "Price", "Unit", "Total"]]
    i = 1
    pageheight = 67 * mm

    for item in purchase.poitem.all().order_by('-id'):
        datalist = []
        datalist.append(str(i))
        i = i + 1

        itemdesc = "<br/>".join(item.description.split("\n"))
        para = Paragraph(f'<font size=7>{itemdesc}</font>', styleN)
        datalist.append(para)

        para.wrapOn(p, 250, 0)
        pageheight = pageheight + para.height

        datalist.append(item.category)
        datalist.append(item.qty)
        datalist.append(round(item.rate, 2))
        datalist.append(item.unit)
        datalist.append(item.total)
        if pageheight / mm < 180:
            data.append(datalist)
        else:
            pagestartposition = 150
            p.setFont("arial", 20)
            p.drawString(100, 100, " Page Continue ...")
            tstyle = TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.gray),
                                 ('BACKGROUND', (0, 0), (-1, 0), (0.9, 0.9, 0.9)),
                                 ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                 ("FONTSIZE", (0, 0), (-1, -1), 8),
                                 ])
            t = Table(data, colWidths=[15, 275, 60, 50, 48, 28, 80])
            t.setStyle(tstyle)
            frame1.addFromList([t], p)
            p.showPage()
            frame1 = Frame(15, 50, 550, A4[1] - pagestartposition, showBoundary=False)
            pageheader()
            pageheight = 67 * mm
            data = [["#", "Description", "Category", "Qty.", "Price", "Unit", "Total"], datalist]

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

    frame1 = Frame(20, 50, 550, A4[1] - pagestartposition, showBoundary=False)
    frame1.addFromList(flow_obj, p)

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
    return FileResponse(buffer, as_attachment=True, filename=f'{purchase.id} - {purchase.supplier}.pdf')
