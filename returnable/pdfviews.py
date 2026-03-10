# Add to views.py

import io
from datetime import datetime
from django.http import FileResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Returnable, ChallanItem, ReceivedChallan, ReceivedItem


@login_required(login_url='/login/')
def returnable_pdf(request, id):
    rc = get_object_or_404(Returnable, id=id)

    printed_by = request.user.get_full_name().upper() or request.user.username.upper()
    printed_at = datetime.now().strftime('%d/%m/%Y %H:%M')

    buffer = io.BytesIO()

    styles = getSampleStyleSheet()
    style_center      = ParagraphStyle('center',      parent=styles['Normal'], alignment=TA_CENTER, fontSize=8)
    style_center_bold = ParagraphStyle('center_bold', parent=styles['Normal'], alignment=TA_CENTER, fontSize=8, fontName='Helvetica-Bold')
    style_left        = ParagraphStyle('left',        parent=styles['Normal'], alignment=TA_LEFT,   fontSize=8)
    style_left_bold   = ParagraphStyle('left_bold',   parent=styles['Normal'], alignment=TA_LEFT,   fontSize=8, fontName='Helvetica-Bold')
    style_right       = ParagraphStyle('right',       parent=styles['Normal'], alignment=TA_RIGHT,  fontSize=8)
    style_title       = ParagraphStyle('title',       parent=styles['Normal'], alignment=TA_CENTER, fontSize=13, fontName='Helvetica-Bold')

    # ── Page header/footer drawn on every page ───────────────────────────────
    def header_footer(canvas, doc):
        canvas.saveState()
        width, height = A4

        # Company name
        canvas.setFont('Helvetica-Bold', 18)
        canvas.drawCentredString(width / 2, height - 12*mm, "H F FLEX PVT. LTD.")

        # Address lines
        canvas.setFont('Helvetica', 8)
        canvas.drawCentredString(width / 2, height - 17*mm,
            "25 Lucky Lark Textile Park, Gardi, Vita, Dist-Sangli Maharashtra")
        canvas.drawCentredString(width / 2, height - 21*mm,
            "Contact: 7447456686  |  hfflexpvtltd@gmail.com")

        # Divider under header
        canvas.setStrokeColor(colors.black)
        canvas.setLineWidth(0.8)
        canvas.line(15*mm, height - 24*mm, width - 15*mm, height - 24*mm)

        # On page 2+ show challan number top-right
        if doc.page > 1:
            canvas.setFont('Helvetica-Bold', 8)
            canvas.drawRightString(width - 15*mm, height - 12*mm,
                f"Returnable Challan # {rc.id}  (contd.)")

        # Bottom divider
        canvas.setStrokeColor(colors.grey)
        canvas.setLineWidth(0.5)
        canvas.line(15*mm, 12*mm, width - 15*mm, 12*mm)

        # Printed by (left) and page number (right)
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(15*mm, 8*mm,
            f"Printed by: {printed_by}  |  {printed_at}")
        canvas.drawRightString(width - 15*mm, 8*mm, f"Page {doc.page}")

        canvas.restoreState()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=32*mm,    # space for header
        bottomMargin=18*mm, # space for footer
    )

    story = []

    # ── Challan title + meta ─────────────────────────────────────────────────
    story.append(Paragraph("Returnable Challan", style_title))
    story.append(Spacer(1, 3*mm))

    meta_data = [
        [
            Paragraph(f"<b>Challan #:</b> {rc.id}", style_left_bold),
            Paragraph(f"<b>Dispatch Date:</b> {rc.dispatch_date.strftime('%d/%m/%Y')}", style_left),
            Paragraph(f"<b>Expected Return:</b> {rc.expected_date.strftime('%d/%m/%Y')}", style_left),
        ],
        [
            Paragraph(f"<b>Transport By:</b> {rc.transportby or '-'}", style_left),
            Paragraph(f"<b>LR No:</b> {rc.recieptnumber or '-'}", style_left),
            Paragraph(f"<b>Vehicle:</b> {rc.vehicle or '-'}", style_left),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[60*mm, 60*mm, 60*mm])
    meta_table.setStyle(TableStyle([
        ('FONTSIZE',        (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING',   (0, 0), (-1, -1), 2),
        ('TOPPADDING',      (0, 0), (-1, -1), 2),
        ('BOX',             (0, 0), (-1, -1), 0.5, colors.grey),
        ('INNERGRID',       (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ('BACKGROUND',      (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 3*mm))

    # ── Delivery / Return Address ────────────────────────────────────────────
    contact_person = rc.party_name.persons.first() if hasattr(rc.party_name, 'persons') else None

    delivery_lines = [
        [Paragraph("<b>Delivery To:</b>", style_left_bold)],
        [Paragraph(f"<b>{rc.party_name.name}</b>", style_left_bold)],
        [Paragraph(f"{rc.address.addname}, {rc.address.add1}", style_left)],
        [Paragraph(f"{rc.address.add2}  Pincode- {rc.address.pincode}", style_left)],
    ]
    if getattr(rc.party_name, 'gst', None):
        delivery_lines.append([Paragraph(f"GST: {rc.party_name.gst}", style_left)])
    if contact_person:
        delivery_lines.append([Paragraph(
            f"Contact: {contact_person.name} ({contact_person.mobile})", style_left)])

    return_lines = [
        [Paragraph("<b>Return Address To:</b>", style_left_bold)],
        [Paragraph("<b>H F FLEX PVT LTD.</b>", style_left_bold)],
        [Paragraph("Factory: 25, Lucky Lark Textile Park, Gardi", style_left)],
        [Paragraph("Vita, Dist: Khanapur, Pincode- 415311", style_left)],
        [Paragraph("GST: 27AADCH3462K1ZF", style_left)],
        [Paragraph("Email: hfflexpvtltd@gmail.com", style_left)],
    ]
    if rc.createdby:
        return_lines.append([Paragraph(
            f"Contact: {rc.createdby.get_full_name().title()}", style_left)])

    addr_table = Table(
        [[
            Table(delivery_lines, colWidths=[85*mm]),
            Table(return_lines,   colWidths=[85*mm]),
        ]],
        colWidths=[90*mm, 90*mm]
    )
    addr_table.setStyle(TableStyle([
        ('VALIGN',    (0, 0), (-1, -1), 'TOP'),
        ('LINEAFTER', (0, 0), (0,  -1), 0.5, colors.grey),
        ('BOX',       (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND',(0, 0), (-1, -1), colors.whitesmoke),
    ]))
    story.append(addr_table)
    story.append(Spacer(1, 4*mm))

    # ── Items Table ──────────────────────────────────────────────────────────
    col_headers = ['#', 'Description', 'Category', 'Qty', 'Rec. Qty', 'Pen. Qty', 'Approx Value']
    col_widths  = [8*mm, 65*mm, 22*mm, 18*mm, 18*mm, 18*mm, 22*mm]

    item_data = [col_headers]
    for i, item in enumerate(rc.challanitem.all(), 1):
        desc = Paragraph(
            f"<b>{item.itemname or ''}</b><br/>"
            f"<font size='7'>{item.description or ''}</font>",
            style_left
        )
        item_data.append([
            str(i),
            desc,
            item.category or '-',
            f"{item.qty:g} {item.unit}",
            f"{item.receivedqty:g}",
            f"{item.pendingqty:g}",
            f"Rs. {item.approxvalue:.2f}",
        ])

    # Totals row
    item_data.append([
        '',
        Paragraph('<b>Total</b>', style_right),
        '',
        Paragraph(f'<b>{rc.totalqty}</b>',        style_center_bold),
        Paragraph(f'<b>{rc.total_rec_qty}</b>',   style_center_bold),
        Paragraph(f'<b>{rc.totalpendingqty}</b>', style_center_bold),
        Paragraph(f'<b>Rs. {rc.totalamount:.2f}</b>', style_left_bold),
    ])

    items_table = Table(item_data, colWidths=col_widths, repeatRows=1)
    items_table.setStyle(TableStyle([
        ('BACKGROUND',     (0, 0),  (-1, 0),  colors.HexColor('#343a40')),
        ('TEXTCOLOR',      (0, 0),  (-1, 0),  colors.white),
        ('FONTNAME',       (0, 0),  (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',       (0, 0),  (-1, -1), 8),
        ('ALIGN',          (0, 0),  (-1, 0),  'CENTER'),
        ('ALIGN',          (2, 1),  (-1, -1), 'CENTER'),
        ('ALIGN',          (0, 1),  (0,  -1), 'CENTER'),
        ('VALIGN',         (0, 0),  (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1),  (-1, -2), [colors.white, colors.HexColor('#f8f9fa')]),
        ('BACKGROUND',     (0, -1), (-1, -1), colors.HexColor('#e9ecef')),
        ('FONTNAME',       (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('GRID',           (0, 0),  (-1, -1), 0.4, colors.grey),
        ('BOTTOMPADDING',  (0, 0),  (-1, -1), 3),
        ('TOPPADDING',     (0, 0),  (-1, -1), 3),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 4*mm))

    # ── Remark ───────────────────────────────────────────────────────────────
    remark_text = rc.remark or '---'
    remark_table = Table(
        [[Paragraph(f'<b><font color="red">Remark: </font></b>{remark_text}', style_left)]],
        colWidths=[180*mm]
    )
    remark_table.setStyle(TableStyle([
        ('BOX',           (0, 0), (-1, -1), 0.5, colors.grey),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
    ]))
    story.append(remark_table)
    story.append(Spacer(1, 6*mm))

    # ── Signature Footer ─────────────────────────────────────────────────────
    created_name = rc.createdby.get_full_name().upper() if rc.createdby else '-'
    created_date = rc.created.strftime('%d/%m/%Y') if rc.created else '-'

    footer_table = Table(
        [[
            Table([
                [Paragraph('<b>Created By</b>', style_center_bold)],
                [Paragraph(created_name,           style_center)],
                [Paragraph(f'Date: {created_date}', style_center)],
            ], colWidths=[85*mm]),
            Paragraph('', style_center),
            Table([
                [Paragraph('<b>Authorised Signatory</b>', style_center_bold)],
                [Spacer(1, 10*mm)],
                [Paragraph('H F FLEX PVT. LTD.', style_center_bold)],
            ], colWidths=[85*mm]),
        ]],
        colWidths=[85*mm, 10*mm, 85*mm]
    )
    footer_table.setStyle(TableStyle([
        ('BOX',    (0, 0), (0, 0),   0.5, colors.grey),
        ('BOX',    (2, 0), (2, 0),   0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(footer_table)

    # ── Build ────────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    buffer.seek(0)

    filename = f"challan-{rc.id}-{rc.party_name.name}.pdf"
    return FileResponse(buffer, as_attachment=False, filename=filename)