from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.forms import modelform_factory, inlineformset_factory
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404

# Create your views here.
from django.urls import reverse

from customer.models import Customer
from myproject.access import accessview
from preorder.filters import PreOrderFilter
from preorder.forms import AddPreOrderForm
from preorder.models import PreOrder, JobName


@login_required(login_url='/login/')
@accessview
def preorderlist(request):
    q = request.GET.get('q', None)
    if q != None:
        ord_list = PreOrder.objects.filter(status=q)
    else:
        ord_list = PreOrder.objects.all()

    myFilter = PreOrderFilter(request.GET, ord_list)
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

    return render(request, 'preorder/preorderlist.html', {'orders': orders, 'myFilter': myFilter, 'total': totalcount})


@login_required(login_url='/login/')
@accessview
def addpreorder(request):
    context = {}
    context['customerlist'] = list(Customer.objects.filter(is_customer=True).values_list('name', flat=True))
    preorder_form = AddPreOrderForm(request.POST or None)
    if request.method == 'POST':
        context['order_form'] = preorder_form
        if preorder_form.is_valid():
            context['order_form'] = preorder_form
            ord = preorder_form.save(commit=False)
            ord.createdby = request.user
            ord.save()
            return HttpResponseRedirect(reverse('preorder:editpreorder', kwargs={'id': ord.id}))
        else:
            return render(request, 'preorder/add.html', context)
    else:
        context['preorder_form'] = preorder_form
        return render(request, 'preorder/add.html', context)


@login_required(login_url='/login/')
@accessview
def editpreorder(request, id=None):
    context = {}
    preorder = get_object_or_404(PreOrder, id=id)
    context['customerlist'] = list(Customer.objects.filter(is_customer=True).values_list('name', flat=True))
    preorder_form = AddPreOrderForm(request.POST or None, instance=preorder)
    inlinejobforms = inlineformset_factory(PreOrder, JobName, fields=["id", "jobname", "qty", "unit",
                                                                      "rate", "preimg","prefile","remark","new_cyl_qty",
                                                                      "cyl_cost","design_charges"],can_delete=True)
    jobforms = inlinejobforms(request.POST or None, request.FILES or None,prefix='jobformset', instance=preorder)
    if request.method == 'POST':
        if preorder_form.is_valid() and jobforms.is_valid():
            context['preorder_form'] = preorder_form
            context['jobforms'] = jobforms
            ord = preorder_form.save(commit=False)
            ord.editedby = request.user
            ord.save()
            jobs = jobforms.save(commit=False)
            for job in jobs:
                if job.id:
                    job.editedby = request.user
                else:
                    job.editedby = request.user
                    job.createdby = request.user
                job.save()
            messages.success(request, 'Preorder save sucessfully.')
            return HttpResponseRedirect(reverse('preorder:editpreorder', kwargs={'id': ord.id}))
        else:
            context['preorder_form'] = preorder_form
            context['jobforms'] = jobforms
            messages.success(request, 'SomeThing Went Wrong')
            return render(request, 'preorder/editpreorder.html', context)
    else:
        context['preorder_form'] = preorder_form
        context['jobforms'] = jobforms
        return render(request, 'preorder/editpreorder.html', context)


@login_required(login_url='/login/')
@accessview
def finalsubmit(request, id=None):
    context = {}
    preorder = get_object_or_404(PreOrder, id=id)
    preorder_form = AddPreOrderForm(request.POST or None, instance=preorder)
    inlinejobforms = inlineformset_factory(PreOrder, JobName, fields=["id", "jobname", "qty", "unit", "rate","preimg",
                                                                      "prefile","remark"],can_delete=True)
    jobforms = inlinejobforms(request.POST or None, prefix='jobformset', instance=preorder)
    if request.method == 'POST':
        if preorder_form.is_valid() and jobforms.is_valid():
            context['preorder_form'] = preorder_form
            context['jobforms'] = jobforms
            ord = preorder_form.save(commit=False)
            ord.editedby = request.user
            ord.final_submition = True
            ord.save()
            jobs = jobforms.save(commit=False)
            for job in jobs:
                if job.id:
                    job.editedby = request.user
                else:
                    job.editedby = request.user
                    job.createdby = request.user
                job.save()
            messages.success(request,"final submition done")
            return HttpResponseRedirect(reverse('preorder:preorderlist'))
        else:
            context['preorder_form'] = preorder_form
            context['jobforms'] = jobforms
            messages.success(request,"something went wrong")
            return render(request, 'preorder/editpreorder.html', context)
    else:
        context['preorder_form'] = preorder_form
        context['jobforms'] = jobforms
        return render(request, 'preorder/editpreorder.html', context)


@login_required(login_url='/login/')
@accessview
def preorderpendinglist(request):
    ord_list = JobName.objects.filter(job__isnull=True)
    totalcount = ord_list.count()
    page = request.GET.get('page', 1)
    paginator = Paginator(ord_list, 200)

    try:
        orders = paginator.page(page)
    except PageNotAnInteger:
        orders = paginator.page(1)
    except EmptyPage:
        orders = paginator.page(paginator.num_pages)

    return render(request, 'preorder/pendinglist.html', {'orders': orders,'total': totalcount})
