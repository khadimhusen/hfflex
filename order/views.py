from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum

from django.contrib import messages
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.forms import inlineformset_factory, modelform_factory
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import datetime
from django.utils import timezone
from production.models import Stockdetail, ProdInput
from .models import Order, Job, JobMaterial, JobProcess, JobImage, JobItemAttribute
from .forms import OrderForm, JobForm, JobFormdetail, JobMaterialForm, JobDetailEditForm, JobProcessForm, JobImageForm, \
    JobItemAttributeForm
from customer.models import Address
from myproject.access import accessview, forceview
from .filters import OrderFilter, JobFilter, JobProcessFilter, JobMaterialFilter


@login_required(login_url='/login/')
@forceview
@accessview
def joblist(request):
    param = request.get_full_path().replace(request.path, "")
    q = request.GET.get('q', None)
    if q != None:
        job_list = Job.objects.filter(jobstatus=q)
    else:
        job_list = Job.objects.all()

    myFilter = JobFilter(request.GET, job_list)
    job_list = myFilter.qs.select_related('joborder', 'itemmaster', 'unit',
                                          'joborder__customer').prefetch_related('jobprocess__process')
    result = job_list.aggregate(Sum('kgqty'))
    kgsum = round(result['kgqty__sum'] or 0, 0)

    page = request.GET.get('page', 1)
    paginator = Paginator(job_list, 200)
    try:
        jobs = paginator.page(page)
    except PageNotAnInteger:
        jobs = paginator.page(1)
    except EmptyPage:
        jobs = paginator.page(paginator.num_pages)
    return render(request, 'job/joblist.html', {'jobs': jobs, 'myFilter': myFilter, 'kgsum': kgsum, 'param': param})


@login_required(login_url='/login/')
@accessview
def jobdetail(request, id):
    job = get_object_or_404(
        Job.objects.select_related('itemmaster', 'unit', 'joborder').prefetch_related(
            'jobimages',
            'jobmaterial',
            'jobmaterial__materialname',
            'jobmaterial__item_mat_type',
            'jobmaterial__item_grade',
            'jobprocess',
            'jobprocess__process',
            'jobprocess__unit',
            'jobprocess__jobreport',
            'jobprocess__jobreport__prodinput__material__materialname',
            'jobprocess__jobreport__prodinput__material__item_mat_type',
            'jobprocess__jobreport__prodinput__material__item_grade',
            'jobprocess__jobreport__output__materialname',
            'jobprocess__jobreport__output__item_mat_type',
            'jobprocess__jobreport__output__item_grade',
            'jobcolors',
        ), id=id)

    # build inputdetail for waste breakdown table
    inputdetail = {}
    for a in job.jobprocess.all():
        for b in a.jobreport.all():
            for c in b.prodinput.all():
                key = c.material.mate_name
                qty = round((-c.wtgain or 0), 3)
                amt = round(((c.material.rate or 0) * (c.inputqty or 0)), 3)
                if key not in inputdetail:
                    inputdetail[key] = {"qty": qty, "input": round((-c.inputqty or 0), 3), "amount": amt}
                else:
                    inputdetail[key]["qty"]    += qty
                    inputdetail[key]["input"]  += round((-c.inputqty or 0), 3)
                    inputdetail[key]["amount"] += amt

            for d in b.output.all():
                key = d.mate_name
                qty = round((d.recieved or 0), 3)
                if key not in inputdetail:
                    inputdetail[key] = {"qty": qty, "input": qty, "amount": 0}
                else:
                    inputdetail[key]["qty"]   += qty
                    inputdetail[key]["input"] += qty

    netinput      = 0
    totalwaitgain = 0
    wastekg       = 0
    for key, val in inputdetail.items():
        if val["qty"] < -0.0001:
            netinput      = round(netinput + val["qty"], 3)
            totalwaitgain = round(totalwaitgain + val["input"], 3)
        elif val["qty"] > 0.0001 and 'WASTE' in key:
            wastekg = round(wastekg + val["qty"], 3)

    # call _production_cost_summary ONCE — avoids 4 separate DB round trips
    cost, netoutput = job._production_cost_summary()
    salecost    = round(netoutput * job.kgrate, 3)
    difference  = round(salecost - cost, 3)
    diff_per_kg = round(difference / netoutput, 3) if netoutput else 0

    wastepercent = 0
    if netinput != 0:
        wastepercent = round((netinput + netoutput) * 100 / netinput, 3)

    first   = Job.objects.values('id').first()
    last    = Job.objects.values('id').last()
    nextjob = Job.objects.values('id').filter(id__gt=id).order_by('-id').last()
    prevjob = Job.objects.values('id').filter(id__lt=id).order_by('-id').first()

    context = {
        'job'          : job,
        'next'         : nextjob,
        'prev'         : prevjob,
        'first'        : first,
        'last'         : last,
        'waste'        : inputdetail,
        'totalwaitgain': totalwaitgain,
        'netinput'     : netinput,
        'netoutput'    : netoutput,
        'grossoutput'  : wastekg + netoutput,
        'wastepercent' : wastepercent,
        'cost'         : cost,
        'salecost'     : salecost,
        'difference'   : difference,
        'diff_per_kg'  : diff_per_kg,
    }

    parentform = modelform_factory(Job, fields=('jobstatus', 'account_clearance_date', 'approvedby'))

    if request.method == 'POST':
        status_form           = parentform(request.POST, instance=job)
        accountclearance_form = parentform(request.POST, instance=job,
                                           initial={"jobstatus": "Unplanned",
                                                    "account_clearance_date": datetime.now(),
                                                    "approvedby": request.user})
        context['status_form']           = status_form
        context['accountclearance_form'] = accountclearance_form

        if status_form.is_valid():
            status_form.save()
            messages.success(request, 'status save sucessfully.')
            return HttpResponseRedirect(reverse('order:jobdetail', kwargs={'id': job.id}))
        elif accountclearance_form.is_valid():
            a = accountclearance_form.save(commit=False)
            a.account_clearance_date = timezone.now()
            a.save()
            messages.success(request, 'order save sucessfully.')
            return redirect('/order/joblist/?q=Account clearance')
        else:
            return HttpResponseRedirect(reverse('order:jobdetail', kwargs={'id': job.id}))
    else:
        context['status_form']           = parentform(instance=job)
        context['accountclearance_form'] = parentform(instance=job,
                                                       initial={"jobstatus": "Unplanned",
                                                                "account_clearance_date": datetime.now(),
                                                                "approvedby": request.user})

    finished_list = []
    for item in job.job_disptached.all():
        first_dispatch = item.dispached.all().first()
        finished_list.append({
            "id"           : item.id,
            "object_id"    : item.object_id,
            "grosswt"      : item.gross_wt,
            "tarewt"       : item.tare_wt,
            "netwt"        : item.recieved,
            "nos"          : item.nos,
            "remark"       : item.remark,
            "dispatched_id": first_dispatch.id if first_dispatch else 0,
        })

    context['finished_list'] = sorted(finished_list, key=lambda k: k['dispatched_id'])
    return render(request, 'job/detail.html', context)


@login_required(login_url='/login/')
@accessview
def jobprint(request, id=None):
    job = get_object_or_404(
        Job.objects.select_related('itemmaster', 'unit', 'joborder')
                   .prefetch_related('jobimages'), id=id)
    context = {
        'job'   : job,
        'images': job.jobimages.all(),
    }
    return render(request, 'print/jobdetailprint.html', context)


@login_required(login_url='/login/')
@accessview
def orderlist(request):
    q = request.GET.get('q', None)
    if q != None:
        ord_list = Order.objects.select_related('customer', 'createdby').filter(status=q)
    else:
        ord_list = Order.objects.select_related('customer', 'createdby').all()

    myFilter = OrderFilter(request.GET, ord_list)
    ord_list = myFilter.qs
    totalcount = ord_list.count()
    page = request.GET.get('page', 1)
    paginator = Paginator(ord_list, 200)

    try:
        orders = paginator.page(page)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)

    return render(request, 'order/orderlist.html', {'orders': orders, 'myFilter': myFilter, 'total': totalcount})


@login_required(login_url='/login/')
@accessview
def orderadd(request):
    context = {}
    if request.method == 'POST':
        order_form = OrderForm(request.POST)
        context['order_form'] = order_form
        if order_form.is_valid():
            ord = order_form.save(commit=False)
            ord.createdby = request.user
            ord.status = "Pending"
            ord.save()
            return HttpResponseRedirect(reverse('order:orderdetailedit', kwargs={'id': ord.id}))
        else:
            return render(request, 'order/add.html', context)
    else:
        order_form = OrderForm(initial={'tax1': 9, 'tax2': 9})
        context['order_form'] = order_form
        return render(request, 'order/add.html', context)


@login_required(login_url='/login/')
@accessview
def orderedit(request, id=None):
    context = {}
    order = get_object_or_404(Order, id=id)
    if request.method == 'POST':
        order_form = OrderForm(request.POST, instance=order)
        context['order_form'] = order_form
        if order_form.is_valid():
            ord = order_form.save(commit=False)
            ord.editedby = request.user
            ord.save()
            return HttpResponseRedirect(reverse('order:orderlist'))
        else:
            return render(request, 'order/edit.html', context)
    else:
        order_form = OrderForm(instance=order)
        context['order_form'] = order_form
        return render(request, 'order/edit.html', context)


@login_required(login_url='/login/')
@accessview
def orderdetail(request, id):
    context = {}
    order = get_object_or_404(Order, id=id)
    context['order'] = order
    return render(request, 'order/detail.html', context)


@login_required(login_url='/login/')
@accessview
def orderdetailedit(request, id):
    context = {}
    order = get_object_or_404(Order, id=id)
    customerid = order.customer.id
    jobformset = inlineformset_factory(Order, Job, form=JobForm, extra=8, )
    user = request.user
    if request.method == 'POST':
        ord = OrderForm(prefix='orderform', instance=order)
        formset1 = jobformset(request.POST, prefix='jobformset', instance=order,
                              form_kwargs={'customerid': customerid, 'createdby': user})
        context['order_form'] = ord
        context['job_forms'] = formset1
        if formset1.is_valid():
            formset1.save()
            messages.success(request, 'order save sucessfully.')
            return HttpResponseRedirect(reverse('order:orderlist'))
        else:
            messages.success(request, 'order not save ')
            return render(request, 'order/edit_order.html', context)
    else:
        if user == order.createdby or user.username == "admin":
            ord = OrderForm(instance=order, prefix='orderform')
            formset1 = jobformset(instance=order, prefix='jobformset',
                                  form_kwargs={'customerid': customerid, 'createdby': user})
            context['order_form'] = ord
            context['job_forms'] = formset1
            return render(request, 'order/edit_order.html', context)
        else:
            messages.success(request,
                             f'You are not allowed to change this order. Only {order.createdby.username} can change it.')
            return HttpResponseRedirect(reverse('order:orderlist'))


@login_required(login_url='/login/')
@accessview
def jobdetailedit(request, id):
    context = {}
    job = get_object_or_404(Job, id=id)
    can_delete = request.user == job.joborder.createdby
    subformset1 = inlineformset_factory(Job, JobMaterial, form=JobMaterialForm, extra=3, can_delete=can_delete)
    subformset2 = inlineformset_factory(Job, JobProcess, form=JobProcessForm, extra=3, can_delete=can_delete)
    subformset3 = inlineformset_factory(Job, JobImage, form=JobImageForm, extra=3, can_delete=can_delete)
    subformset4 = inlineformset_factory(Job, JobItemAttribute, form=JobItemAttributeForm, extra=3,
                                        can_delete=can_delete)

    if request.method == 'POST':
        mainform = JobDetailEditForm(request.POST, instance=job)
        formset1 = subformset1(request.POST, prefix='jobrawmaterial', instance=job)
        formset2 = subformset2(request.POST, prefix='jobprocess', instance=job)
        formset3 = subformset3(request.POST, request.FILES, prefix='jobimage', instance=job)
        formset4 = subformset4(request.POST, prefix='jobattr', instance=job)
        context['mainform'] = mainform
        context['subforms1'] = formset1
        context['subforms2'] = formset2
        context['subforms3'] = formset3
        context['subforms4'] = formset4
        if formset1.is_valid() and mainform.is_valid() and formset2.is_valid() \
                and formset3.is_valid() and formset4.is_valid():
            try:
                mainform.save()
                formset1.save()
                formset2.save()
                formset3.save()
                formset4.save()

                return HttpResponseRedirect(reverse('order:jobdetail', kwargs={'id': id}))
            except:
                messages.warning(request, 'something gone wrong')

                return render(request, 'job/edit.html', context)
        else:
            return render(request, 'job/edit.html', context)
    else:
        mainform = JobDetailEditForm(instance=job)
        formset1 = subformset1(prefix='jobrawmaterial', instance=job)
        formset2 = subformset2(prefix='jobprocess', instance=job)
        formset3 = subformset3(prefix='jobimage', instance=job)
        formset4 = subformset4(prefix='jobattr', instance=job)
        context['mainform'] = mainform
        context['subforms1'] = formset1
        context['subforms2'] = formset2
        context['subforms3'] = formset3
        context['subforms4'] = formset4
        return render(request, 'job/edit.html', context)


@login_required(login_url='/login/')
@accessview
def processlist(request, status=None):
    param = request.get_full_path().replace(request.path, "")
    q = status
    if status == 'All':
        proc_list = JobProcess.objects.select_related('job', 'job__itemmaster', 'job__itemmaster__itemcustomer',
                                                      'process',
                                                      'unit').prefetch_related(
            'jobreport', 'jobreport__unit', ).all().order_by('-job__film_size')
    else:
        proc_list = JobProcess.objects.select_related('job', 'job__itemmaster', 'job__itemmaster__itemcustomer',
                                                      'process',
                                                      'unit').prefetch_related(
            'jobreport', 'jobreport__unit', ).filter(process__process=status).order_by('-job__film_size')

    myFilter = JobProcessFilter(request.GET, proc_list)
    proc_list = myFilter.qs
    totalqty = proc_list.aggregate(Sum('qty'))
    totalqty['qty__sum'] = round((totalqty['qty__sum'] or 0))
    page = request.GET.get('page', 1)
    paginator = Paginator(proc_list, 100)
    try:
        process = paginator.page(page)
    except PageNotAnInteger:
        process = paginator.page(1)
    except EmptyPage:
        process = paginator.page(paginator.num_pages)

    return render(request, 'process/processlist.html',
                  {'process': process, 'myFilter': myFilter, 'q': q, 'totalqty': totalqty, 'param': param})


@login_required(login_url='/login/')
@accessview
def jobmateriallist(request):
    q = request.GET.get('q', None)
    if q != None:
        jobmaterial_list = JobMaterial.objects.select_related('materialname', 'item_mat_type',
                                                              'item_grade').filter(jobstatus=q).order_by("-size")
    else:
        jobmaterial_list = JobMaterial.objects.select_related('materialname', 'item_mat_type',
                                                              'item_grade').all().order_by("-size")
    myFilter = JobMaterialFilter(request.GET, jobmaterial_list)
    jobmaterial_list = myFilter.qs
    totalcount = jobmaterial_list.count()

    page = request.GET.get('page', 1)
    paginator = Paginator(jobmaterial_list, 100)
    try:
        jobmaterials = paginator.page(page)
    except PageNotAnInteger:
        jobmaterials = paginator.page(1)
    except EmptyPage:
        jobmaterials = paginator.page(paginator.num_pages)
    return render(request, 'jobmaterial/list.html',
                  {'jobmaterials': jobmaterials, 'total': totalcount, 'myFilter': myFilter})


@login_required(login_url='/login/')
def load_address(request):
    customer_id = request.GET.get('customer')
    addresses = Address.objects.filter(customer_id=customer_id).order_by('addname')
    return render(request, 'customer/address_dropdown_list_options.html', {'addresses': addresses})


@login_required(login_url='/login/')
def jobdcancel(request, id=None):
    if request.user.username == "admin" or request.user.username == "khadimhusen":
        job = get_object_or_404(Job, id=id)
        deletematerial = job.jobmaterial.all()
        deleteprocess = job.jobprocess.all()
        deletecolors = job.jobcolors.all()
        deleteimages = job.jobimages.all()
        try:
            deletematerial.delete()
            deleteprocess.delete()
            deletecolors.delete()
            deleteimages.delete()
            Job.objects.filter(id=id).update(jobstatus="Cancelled")
        except:
            messages.warning(request,
                             'something gone wrong, Please check alloted material or production report entry. if any delete that.')
            return HttpResponseRedirect(reverse('order:jobdetail', kwargs={'id': id}))

        messages.warning(request, 'Job cancelled ')
        return HttpResponseRedirect(reverse('order:joblist'))
    else:
        messages.warning(request, 'Only admin can cancel job')
        return HttpResponseRedirect(reverse('order:jobdetail', kwargs={'id': id}))


@login_required(login_url='/login/')
@accessview
def rate(request):
    context = {}
    rateform = modelform_factory(Stockdetail, fields=["materialname", "item_mat_type", "item_grade", "rate"])
    if request.method == 'POST':

        materialname = request.POST['materialname']
        item_mat_type = request.POST['item_mat_type']
        item_grade = request.POST['item_grade']
        rate = request.POST['rate']
        obj = Stockdetail.objects.filter(materialname=materialname,
                                         item_mat_type=item_mat_type,
                                         item_grade=item_grade,
                                         rate__isnull=True)
        obj.update(rate=rate)
        obj = Stockdetail.objects.filter(materialname=materialname,
                                         item_mat_type=item_mat_type,
                                         item_grade=item_grade,
                                         rate__lte=0.1)
        obj.update(rate=rate)

        context["mainform"] = rateform()
        return render(request, 'other/rate.html', context)
    else:
        context["mainform"] = rateform()
        return render(request, 'other/rate.html', context)


@login_required(login_url='/login/')
@accessview
def unplannedtopending(request):
    a = Job.objects.filter(jobstatus="Unplanned")
    a.update(jobstatus="Pending")
    messages.success(request, "done")
    return HttpResponseRedirect(reverse('order:joblist'))


@login_required(login_url='/login/')
@accessview
def planninglist(request, status=None):
    param = request.get_full_path().replace(request.path, "")
    q = status
    if status == 'All':
        proc_list = JobProcess.objects.select_related('job', 'job__itemmaster', 'job__itemmaster__itemcustomer',
                                                      'process',
                                                      'unit').prefetch_related(
            'jobreport', 'jobreport__unit', ).all().order_by('-srno')
    else:
        proc_list = JobProcess.objects.select_related('job', 'job__itemmaster', 'job__itemmaster__itemcustomer',
                                                      'process',
                                                      'unit').prefetch_related(
            'jobreport', 'jobreport__unit', ).filter(machine__machinename=status).order_by('-srno')

    myFilter = JobProcessFilter(request.GET, proc_list)
    proc_list = myFilter.qs
    totalqty = proc_list.aggregate(Sum('qty'))
    totalqty['qty__sum'] = round((totalqty['qty__sum'] or 0))
    page = request.GET.get('page', 1)
    paginator = Paginator(proc_list, 100)
    try:
        process = paginator.page(page)
    except PageNotAnInteger:
        process = paginator.page(1)
    except EmptyPage:
        process = paginator.page(paginator.num_pages)

    return render(request, 'process/planninglist.html',
                  {'process': process, 'myFilter': myFilter, 'q': q, 'totalqty': totalqty, 'param': param})


def removedisptachapproval(request, id=None):
    job = get_object_or_404(Job, id=id)
    job.dispatch_approval = False
    job.dispatch_approval_date = None
    job.save()
    return HttpResponseRedirect(reverse('production:dispatchapprovalpending'))
