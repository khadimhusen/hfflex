from django.shortcuts import render, get_object_or_404
from customer.models import Customer
from .models import Po, PoItem, Term
from employee.models import Department
from django.contrib.auth.decorators import login_required
from myproject.access import accessview
from .filters import PoFilter, PoItemFilter
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .forms import PoForm, PoItemForm, PoApprovalForm, PoImageForm, PoItemFormMarketing, ExpectedDateForm
from django.urls import reverse
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.forms import inlineformset_factory
from io import BytesIO
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from datetime import datetime
from django.forms import modelform_factory


@login_required(login_url='/login/')
@accessview
def purchaselist(request):
    param = request.get_full_path().replace(request.path, "")
    q = request.GET.get('q', None)

    if Department.objects.filter(department_name="can_see_all_po", user=request.user).exists():
        if q != None:
            po_list = Po.objects.filter(state=q)
        else:
            po_list = Po.objects.all()
    else:
        if q != None:
            po_list = Po.objects.filter(state=q, createdby=request.user)
        else:
            po_list = Po.objects.filter(createdby=request.user)

    myFilter = PoFilter(request.GET, po_list)
    po_list = myFilter.qs.select_related('supplier', 'createdby', 'approvedby')

    page = request.GET.get('page', 1)
    paginator = Paginator(po_list, 100)
    try:
        pos = paginator.page(page)
    except PageNotAnInteger:
        pos = paginator.page(1)
    except EmptyPage:
        pos = paginator.page(paginator.num_pages)

    return render(request, 'purchase/purchaselist.html', {'pos': pos, 'myFilter': myFilter, 'param': param})


@login_required(login_url='/login/')
@accessview
def purchasenew(request):
    context = {}
    if request.method == 'POST':

        po_form = PoForm(request.POST)
        context['po_form'] = po_form
        if po_form.is_valid():
            po = po_form.save(commit=False)
            po.createdby = request.user
            po.status = "Pending"
            po.save()
            po_form.save_m2m()
            return HttpResponseRedirect(reverse('purchase:purchaseedit', kwargs={'id': po.id}))
        else:
            print(po_form.errors)
            return render(request, 'purchase/purchasenew.html', context)
    else:
        po_form = PoForm()
        context['po_form'] = po_form
        return render(request, 'purchase/purchasenew.html', context)


@login_required(login_url='/login/')
@accessview
def purchaseedit(request, id=None):
    context = {}
    po = get_object_or_404(Po, id=id)

    if Department.objects.filter(department_name="can_add_price",user=request.user).exists():
        can_add_price = True
        poitemformset = inlineformset_factory(Po, PoItem, PoItemForm, extra=12, max_num=20, can_delete=True)
    else:
        can_add_price = False
        poitemformset = inlineformset_factory(Po, PoItem, PoItemFormMarketing, extra=12, max_num=20, can_delete=True)

    context["can_add_price"] = can_add_price

    if request.method == 'POST':
        mainform = PoForm(request.POST, instance=po)
        poitemform = poitemformset(request.POST or None, prefix="poitemform", instance=po)
        context['mainform'] = mainform
        context['poitemform'] = poitemform
        if mainform.is_valid() and poitemform.is_valid():
            try:
                mainform.save(commit=False)
                mainform.editedby = request.user
                mainform.save()
                if can_add_price:
                    poitemform.save()
                else:
                    instances = poitemform.save(commit=False)

                    for instance in instances:
                        instance.rate = (instance.rate or 0)
                        instance.save()
                    poitemform.save_m2m()
                return HttpResponseRedirect(reverse('purchase:purchasedetail', kwargs={'id': id}))
            except:
                messages.warning(request, 'something gone wrong')
                print("mainform", mainform.errors)
                print("poitemform", poitemform.errors)
                return render(request, 'purchase/edit.html', context)
        else:
            print("mainform", mainform.errors)
            print("poitemform", poitemform.errors)
            return render(request, 'purchase/edit.html', context)
    else:
        mainform = PoForm(instance=po)
        poitemform = poitemformset(prefix="poitemform", instance=po)
        context['mainform'] = mainform
        context['poitemform'] = poitemform
        return render(request, 'purchase/edit.html', context)


@login_required(login_url='/login/')
@accessview
def purchasedetail(request, id=None):
    context = {}
    po = get_object_or_404(Po, id=id)
    poimageform = PoImageForm(instance=po)
    poapprovalform = PoApprovalForm(instance=po, initial={'approvedby': request.user})
    poexpecteddateform = ExpectedDateForm()

    pomaterial = po.jobmaterial.all().order_by("materialname", "item_mat_type", "item_grade", "size", "micron")
    mat = [{"job": m.job, "material": m.material, "qty": m.orderedqty} for m in pomaterial]

    context["poimageform"] = poimageform
    context["po"] = po
    context["poapprovalform"] = poapprovalform
    context["mat"] = mat
    context["followupform"] = poexpecteddateform
    return render(request, "purchase/detail.html", context)


@login_required(login_url='/login/')
@accessview
def render_pdf(request, id=None):
    print(request.user)
    context = {}
    print("hi")
    po = get_object_or_404(Po, id=id)
    print("print", po)
    context["po"] = po
    template_path = 'purchase/purchasepdf.html'
    pdf = render_to_pdf('purchase/purchasepdf.html', context)
    return render(request, template_path, context)


def render_to_pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()

    # This part will create the pdf.
    pdf = pisa.pisaDocument(BytesIO(html.encode("ISO-8859-1")), result)
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return None


@login_required(login_url='/login/')
@accessview
def poapproval(request, id=None):
    context = {}
    po = get_object_or_404(Po, id=id)
    if request.method == "POST" and request.user:
        form = PoApprovalForm(request.POST, instance=po)
        context["poapprovalform"] = form
        if form.is_valid():
            forminstance = form.save(commit=False)
            forminstance.approvedby = request.user
            forminstance.approve_date = datetime.now()
            forminstance.save()
            messages.success(request, 'order save sucessfully.')
            return HttpResponseRedirect(reverse('purchase:purchasedetail', kwargs={'id': po.id}))

    return HttpResponseRedirect(reverse('purchase:purchasedetail', kwargs={'id': po.id}))


@login_required(login_url='/login/')
@accessview
def removepoapproval(request, id=None):
    po = get_object_or_404(Po, id=id)
    po.approvedby = None
    po.approve_date = None
    po.save()
    return HttpResponseRedirect(reverse('purchase:purchasedetail', kwargs={'id': id}))


@login_required(login_url='/login/')
@accessview
def addpoimage(request, id=None):
    po = get_object_or_404(Po, id=id)

    if request.method == "POST":
        form = PoImageForm(request.POST or None, request.FILES or None)
        if form.is_valid():
            a = form.save(commit=False)
            a.po = po
            a.createdby = request.user
            a.save()
            messages.success(request, 'Image save sucessfully.')
            return HttpResponseRedirect(reverse('purchase:purchasedetail', kwargs={'id': po.id}))
        else:
            print("form error", form.errors)
            return HttpResponseRedirect(reverse('purchase:purchasedetail', kwargs={'id': po.id}))
    return HttpResponseRedirect(reverse('purchase:purchasedetail', kwargs={'id': po.id}))


@login_required(login_url='/login/')
@accessview
def poitemlist(request):
    param = request.get_full_path().replace(request.path, "")
    q = request.GET.get('q', None)
    if q != None:
        poitem_list = PoItem.objects.filter(state=q)
    else:
        poitem_list = PoItem.objects.all()

    myFilter = PoItemFilter(request.GET, poitem_list)
    poitem_list = myFilter.qs.select_related('purchaseorder__supplier', 'createdby')

    page = request.GET.get('page', 1)
    paginator = Paginator(poitem_list, 100)
    try:
        pos = paginator.page(page)
    except PageNotAnInteger:
        pos = paginator.page(1)
    except EmptyPage:
        pos = paginator.page(paginator.num_pages)
    return render(request, 'purchase/poitemlist.html', {'pos': pos, 'myFilter': myFilter, 'param': param})


@login_required(login_url='/login/')
@accessview
def setcatogery(request):
    context = {}
    catform = modelform_factory(PoItem, fields=["category"])
    supform = modelform_factory(Customer, fields=["name"])

    if request.method == "POST":
        print("REAUST", request.POST)
        sup = Customer.objects.get(name__icontains=request.POST["name"])
        print("sup", sup)
        if sup:
            PoItem.objects.filter(purchaseorder__supplier=sup).update(category=request.POST["category"])

    context["catform"] = catform()
    context["supform"] = supform()
    return render(request, "purchase/setcategory.html", context)


import io
from django.http import FileResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4


def some_view(request):
    # Create a file-like buffer to receive PDF data.
    buffer = io.BytesIO()

    # Create the PDF object, using the buffer as its "file."
    p = canvas.Canvas(buffer, pagesize=A4, bottomup=0)

    # Draw things on the PDF. Here's where the PDF generation happens.
    # See the ReportLab documentation for the full list of functionality.
    for i in range(100):
        p.drawString(50, 50 * i, "Hello world hffsasdadlex.")
        p.showPage()
    # Close the PDF object cleanly, and we're done.

    p.save()

    # FileResponse sets the Content-Disposition header so that browsers
    # present the option to save the file.
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=False, filename='hello.pdf')


@login_required(login_url='/login/')
@accessview
def deepclonepurchase(request, id=None):
    context = {}
    po = get_object_or_404(Po, id=id)

    if Department.objects.filter(department_name="can_add_price",user=request.user).exists():
        can_add_price = True
        poitemformset = inlineformset_factory(Po, PoItem, PoItemForm, extra=12, max_num=12, can_delete=True)
    else:
        can_add_price = False
        poitemformset = inlineformset_factory(Po, PoItem, PoItemFormMarketing, extra=12, max_num=12, can_delete=True)

    context["can_add_price"] = can_add_price

    if request.method == 'POST':
        mainform = PoForm(request.POST)
        poitemform = poitemformset(request.POST or None, prefix="poitemform", instance=po)
        context['mainform'] = mainform
        context['poitemform'] = poitemform
        if mainform.is_valid() and poitemform.is_valid():
            try:
                a = mainform.save(commit=False)
                a.status = "Pending"
                a.createdby = request.user
                a.editedby = request.user
                a.save()
                poitems = po.poitem.all()

                for i in poitems:
                    PoItem.objects.create(
                        purchaseorder=a,
                        description=i.description,
                        category=i.category,
                        qty=i.qty,
                        unit=i.unit,
                        rate=i.rate,
                        rec_qty=0,
                        createdby=request.user,
                    )

                messages.warning(request, 'Po cloned successfully')

                return HttpResponseRedirect(reverse('purchase:purchasedetail', kwargs={'id': a.id}))
            except Exception as inst:
                print(inst.args)
                messages.warning(request, 'something gone wrong')
                return render(request, 'purchase/edit.html', context)
        else:
            print("mainform", mainform.errors)
            print("poitemform", poitemform.errors)
            return render(request, 'purchase/edit.html', context)
    else:
        mainform = PoForm(instance=po)
        poitemform = poitemformset(prefix="poitemform", instance=po)
        context['mainform'] = mainform
        context['poitemform'] = poitemform
        return render(request, 'purchase/edit.html', context)


def poexpeteddate(request, id):
    po = get_object_or_404(Po, id=id)
    purchase = Po.objects.filter(id=id)
    print("request", request.POST)
    if request.method == "POST":
        form = ExpectedDateForm(request.POST or None)
        if form.is_valid():
            a = form.save(commit=False)
            a.po = po
            a.createdby = request.user
            a.save()

            purchase.update(delivery_date=a.expected_date)
            messages.success(request, 'Schedule save sucessfully.')
            return HttpResponseRedirect(reverse('purchase:purchasedetail', kwargs={'id': po.id}))
        else:
            print("form error", form.errors)
            return HttpResponseRedirect(reverse('purchase:purchasedetail', kwargs={'id': po.id}))
    return HttpResponseRedirect(reverse('purchase:purchasedetail', kwargs={'id': po.id}))
