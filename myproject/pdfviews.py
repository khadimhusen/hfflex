from django.shortcuts import get_object_or_404
from .models import Po
from django.http import FileResponse
from reportlab.pdfgen import canvas
import io
from reportlab.lib.pagesizes import A4, A0
from reportlab.lib.colors import red, seagreen, black, orange, yellow
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import reportlab.rl_config
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Frame, Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

reportlab.rl_config.warnOnMissingFontGlyphs = 0

# pdfmetrics.registerFont(TTFont('abc', "ARLRDBD.ttf"))
pdfmetrics.registerFont(TTFont('clarendon', "CLARENDON BLK BT BLACK.ttf"))
pdfmetrics.registerFont(TTFont('brush', "BRUSHSCI.ttf"))



def popdf(request, id):
    purchase = get_object_or_404(Po, id=id)
    buffer = io.BytesIO()

    p = canvas.Canvas(buffer, pagesize=A4, bottomup=1)
    p.setLineWidth(1)
    p.setStrokeColor(yellow)
    p.setFillColor(yellow)
    cpath = p.beginPath()
    cpath.moveTo(0, A4[1])
    cpath.lineTo(80, A4[1])
    cpath.lineTo(0, A4[1] - 80)
    cpath.lineTo(0, A4[1])
    p.drawPath(cpath, stroke=1, fill=1)
    p.setFillColor(orange)
    p.setStrokeColor(orange)
    cpath = p.beginPath()
    cpath.moveTo(0, A4[1] - 0)
    cpath.lineTo(73, A4[1] - 0)
    cpath.lineTo(0, A4[1] - 73)
    cpath.lineTo(0, A4[1] - 0)
    p.drawPath(cpath, stroke=1, fill=1)
    cpath = p.beginPath()
    cpath.moveTo(10, A4[1] - 100)
    cpath.lineTo(10, A4[1] - 180)
    cpath.moveTo(315, A4[1] - 100)
    cpath.lineTo(315, A4[1] - 180)
    cpath.moveTo(5, A4[1] - 190)
    cpath.lineTo(A4[0] - 5, A4[1] - 190)
    cpath.moveTo(5, A4[1] - 90)
    cpath.lineTo(A4[0] - 5, A4[1] - 90)
    p.drawPath(cpath, stroke=1, fill=0)
    p.setFont("Helvetica", 10)
    p.setFillColorRGB(0.0, 0.2, 0.4)
    p.drawRightString(A4[0] - 140, A4[1] - 20, 'Purchase Order No:- ')
    p.setFont("Helvetica", 16)
    p.drawString(A4[0] - 140, A4[1] - 20, f'# {((6 - len(str(purchase.id))) * "0") + str(purchase.id)}')

    p.setFont("Helvetica", 10)
    p.drawRightString(A4[0] - 140, A4[1] - 35, 'Date:- ')

    p.drawString(A4[0] - 140, A4[1] - 35, purchase.created.strftime("%d/%m/%Y"))
    p.drawRightString(A4[0] - 140, A4[1] - 50, 'Expteced Delivery:- ')
    p.drawString(A4[0] - 140, A4[1] - 50, purchase.delivery_date.strftime("%d/%m/%Y"))
    p.drawRightString(A4[0] - 140, A4[1] - 65, 'Transportation:- ')
    p.drawString(A4[0] - 140, A4[1] - 65, purchase.transport)
    p.drawRightString(A4[0] - 140, A4[1] - 80, 'Payment Terms:- ')
    p.drawString(A4[0] - 140, A4[1] - 80, str(purchase.payment_terms or ""))
    p.setFillColorRGB(0.95, 0.95, 0.95)
    p.setFont("clarendon", 25)
    p.drawCentredString(A4[0] / 2 - 98, A4[1] - 25, "H F Flex Pvt. Ltd.")
    p.setFillColorRGB(0.80, 0, 0)
    p.drawCentredString(A4[0] / 2 - 100, A4[1] - 28, "H F Flex Pvt. Ltd.")
    p.setFillColorRGB(0.4, 0.4, 0.6)
    p.setFont("Helvetica", 10)
    p.drawCentredString(A4[0] / 2 - 100, A4[1] - 42,
                        "25,Lucky Lark Textile Park, Gardi, Vita")
    p.drawCentredString(A4[0] / 2 - 100, A4[1] - 55, "Tal- Khanapur, Dist- Sangli, Maharashtra-415311")
    p.drawCentredString(A4[0] / 2 - 100, A4[1] - 68, "Contact:- 8552827683,9765643576,")
    p.drawCentredString(A4[0] / 2 - 100, A4[1] - 81, " Email:- hfflexpvtltd@gmail.com, Website: www.hfflex.co.in")
    p.drawString(20, A4[1] - 105, 'Purchase Order To:-')
    p.drawString(325, A4[1] - 105, 'Delivery To:-')
    p.setFillColorRGB(0.80, 0, 0)
    p.setFont("Helvetica", 12)
    p.drawString(20, A4[1] - 120, f'{purchase.supplier}')
    p.drawString(325, A4[1] - 120, 'H F FLEX PVT. LTD.')
    p.setFont("Helvetica", 10)
    p.setFillColorRGB(0.0, 0.2, 0.4)

    item = purchase.supplier.addresses.first()
    p.drawString(20, A4[1] - 130, f'{item.addname or ""}-{item.add1 or ""}')
    p.drawString(20, A4[1] - 143, f'{item.add2 or ""}-{item.pincode or ""}')
    if purchase.supplier.gst:
        p.drawString(20, A4[1] - 156, f'GST:- {purchase.supplier.gst or ""}')
    person = purchase.supplier.persons.first()
    if person:
        p.drawString(20, A4[1] - 169, f'ContactPerson: -{person.name or ""} ({person.mobile or ""})')
    else:
        p.drawString(20, A4[1] - 169, "ContactPerson: -")

    p.drawString(20, A4[1] - 182, f'Email: -{purchase.supplier.email or ""})')
    p.drawString(325, A4[1] - 130, f'{purchase.delivery_at.addname or ""}-{purchase.delivery_at.add1 or ""}')
    p.drawString(325, A4[1] - 143, f'{purchase.delivery_at.add2 or ""}-{purchase.delivery_at.pincode or ""}')
    p.drawString(325, A4[1] - 156, 'Gst:- 27AADCH3462K1ZF')
    p.drawString(325, A4[1] - 169,
                 f'ContactPerson: -{purchase.createdby.profile.prefix or ""} {purchase.createdby.get_full_name() or ""}-{purchase.createdby.profile.mobile or ""}')
    p.drawString(325, A4[1] - 182, 'Email: -hfflexpvtltd@gmail.com')

    flow_obj = []
    styles = getSampleStyleSheet()

    styleN = styles["BodyText"]

    data = [["Srno", "Description", "Category", "Qty.", "Price", "Unit", "Total"]]
    i = 1
    for item in purchase.poitem.all():
        datalist = []
        datalist.append(str(i))
        i = i + 1
        datalist.append(Paragraph(f'<font size=8>{item.description}</font>', styleN))
        datalist.append(item.category)
        datalist.append(item.qty)
        datalist.append(item.rate)
        datalist.append(item.unit)
        datalist.append(item.total)
        data.append(datalist)
    else:

        terms = ""
        for term in purchase.poterm.all():
            terms = terms + term.term + "<br />"

    termsandcondition = Paragraph(f'<font  size=8>{terms}</font>', styleN)

    data.append(["", "Terms & Conditions", "Total Qty", purchase.totalqty, "SubTotal", "", f'Rs. {purchase.pototal}'])
    data.append([termsandcondition, "", "", "", f'CGST {purchase.tax1} %', "",  f'Rs. {purchase.cgst}'])
    data.append(["", "", "", "", f'SGST {purchase.tax2} %', "", f'Rs. {purchase.sgst}'])
    data.append([Paragraph(f' {purchase.inword}',styleN), "", "", "", "Grand Total", "", f'Rs. {purchase.grosstotal}'])
    data.append([Paragraph(f' <font color=red><b>Remark:-</b> {purchase.remark or ""}</font>',styleN), "", "", "", "", "", ""])
    data.append(["Created by", "", "", "Approved by", "", "", ""])
    data.append([purchase.createdby, "", "", purchase.approvedby, "", "", ""])
    data.append([purchase.created.strftime("%d-%m-%Y   %H:%I %p"), "",
                 "", purchase.approve_date.strftime("%d-%m-%Y   %H:%I %p") if purchase.approve_date else '', "", "",
                 ""])

    tstyle = TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.gray),
                         ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                         ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                         ("FONTSIZE", (0, 0), (-1, -1), 8),
                         ('TEXTCOLOR', (0, 0), (0, 0), colors.gray),
                         ('SPAN', (0, -1), (2, -1)),
                         ('SPAN', (3, -1), (6, -1)),
                         ('SPAN', (0, -2), (2, -2)),
                         ('SPAN', (3, -2), (6, -2)),
                         ('SPAN', (0, -3), (2, -3)),
                         ('SPAN', (3, -3), (6, -3)),
                         ('SPAN', (0, -4), (6, -4)),
                         ('SPAN', (0, -5), (3, -5)),
                         ('SPAN', (-3, -5), (-2, -5)),
                         ('SPAN', (-3, -6), (-2, -6)),
                         ('SPAN', (4, -7), (5, -7)),
                         ('SPAN', (0, -6), (3, -7)),
                         ('SPAN', (-3, -8), (-2, -8)),

                         ])

    t = Table(data, colWidths=[20, 220, 70, 50, 50, 30, 80])
    t.setStyle(tstyle)
    flow_obj.append(t)

    frame1 = Frame(20, 80, 550, 550, showBoundary=0)
    frame1.addFromList(flow_obj, p)

    if not purchase.approvedby:
        p.setFillColorRGB(0.80, 0, 0, 0.3)
        p.setFont("Helvetica", 30)

        p.drawCentredString(A4[0] / 2, 20, "Pending for Approval")


    else:
        p.setFillColorRGB(0, 0.8, 0, 0.3)
        p.setFont("Helvetica", 30)

        p.drawCentredString(A4[0] / 2, 20, "Approved")

    p.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f'{purchase.id} - {purchase.supplier}.pdf')
