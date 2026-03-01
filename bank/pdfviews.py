from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from reportlab.lib.pagesizes import A4
from myproject.access import accessview
from .models import Cheque
from django.http import FileResponse
from reportlab.pdfgen import canvas
import io
from reportlab.lib.units import mm
import reportlab.rl_config

reportlab.rl_config.warnOnMissingFontGlyphs = 1


@login_required(login_url='/login/')
@accessview
def chequepdf(request, id):
    cheque = get_object_or_404(Cheque, id=id)
    buffer = io.BytesIO()
    pagesize = (110 * mm, 220 * mm)

    p = canvas.Canvas(buffer, pagesize=pagesize, bottomup=1)
    p.rotate(-90)

    p.setFont("Helvetica", 12)
    p.setFillColorRGB(0.0, 0.0, 0.0)
    if cheque.party:
        p.drawString(-200 * mm, 79 * mm, f'{cheque.party}')
    p.drawString(-188 * mm, 70 * mm, f'{cheque.amountinword}')
    if cheque.amountint:
        p.drawCentredString(-43 * mm, 63 * mm, f'**{cheque.amountint}**')
    t = p.beginText()
    if cheque.bank.id==1:
        t.setTextOrigin(-62 * mm, 93 * mm)
        t.setCharSpace(9.8)
    else:
        t.setTextOrigin(-57 * mm, 93 * mm)
        t.setCharSpace(7.7)
    if cheque.cheque_date:
        t.textLine(f'{cheque.cheque_date.strftime("%d%m%Y")}')
    p.drawText(t)

    p.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f'{cheque.number} - {cheque.party}.pdf')


@login_required(login_url='/login/')
@accessview
def chequepdf1(request, id):
    cheque = get_object_or_404(Cheque, id=id)
    buffer = io.BytesIO()
    pagesize = (110 * mm, 220 * mm)

    p = canvas.Canvas(buffer, pagesize=pagesize, bottomup=1)
    p.rotate(90)
    p.setFont("Helvetica", 12)
    p.setFillColorRGB(0.0, 0.0, 0.0)
    p.drawString(45, -75, f'{cheque.party}')
    p.drawString(75, -105, f'{cheque.amountinword}')
    p.drawString(520, -130, f'**{cheque.amount}**')
    t = p.beginText()
    t.setTextOrigin(490, -35)
    t.setCharSpace(10.5)
    t.textLine(f'{cheque.cheque_date.strftime("%d%m%Y")}')
    p.drawText(t)

    p.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f'{cheque.id} - {cheque.party}.pdf')


def a4pdf(request, id):
    cheque = get_object_or_404(Cheque, id=id)
    buffer = io.BytesIO()
    pagesize = (110 * mm, 220 * mm)

    p = canvas.Canvas(buffer, pagesize=A4, bottomup=1)
    p.rotate(-90)

    p.setFont("Helvetica", 13)
    p.setFillColorRGB(0.0, 0.0, 0.0)
    if cheque.party:
        p.drawString(-205 * mm, 84 * mm, f'{cheque.party}')
    p.drawString(-200 * mm, 73 * mm, f'{cheque.amountinword}')
    if cheque.amountint:
        p.drawCentredString(-35 * mm, 65 * mm, f'**{cheque.amountint}**')
    t = p.beginText()
    if cheque.bank.id==1:
        t.setTextOrigin(-162, 99 * mm)
        t.setCharSpace(11.5)
    else:
        t.setTextOrigin(-150, 98 * mm)
        t.setCharSpace(10.5)
    if cheque.cheque_date:
        t.textLine(f'{cheque.cheque_date.strftime("%d%m%Y")}')
    p.drawText(t)

    p.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f'{cheque.number} - {cheque.party}.pdf')
