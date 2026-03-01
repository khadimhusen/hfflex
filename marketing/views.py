from django.core.paginator import Paginator
from django.forms import inlineformset_factory
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .filters import LeadFilter, RouteFilter, BunchFilter
from .models import Lead, RouteCustomer, Route, Bunch
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from .forms import LeadForm, RouteForm, RouteCustomerForm, BunchForm, RouteFeedbackForm
from myproject.access import accessview
from django.contrib.auth.decorators import login_required
from django.views.generic import CreateView


@login_required(login_url='/login/')
@accessview
def leadlist(request):
    lead_list = Lead.objects.filter()
    myFilter = LeadFilter(request.GET, lead_list)
    lead_list = myFilter.qs

    page = request.GET.get('page', 1)
    paginator = Paginator(lead_list, 100)
    try:
        leads = paginator.page(page)
    except PageNotAnInteger:
        leads = paginator.page(1)
    except EmptyPage:
        leads = paginator.page(paginator.num_pages)
    return render(request, 'lead/leadlist.html', {'leads': leads, 'myFilter': myFilter})


@login_required(login_url='/login/')
@accessview
def leadadd(request):
    context = {}
    if request.method == 'POST':
        leadform = LeadForm(request.POST)
        context['leadform'] = leadform
        if leadform.is_valid():
            a = leadform.save(commit=False)
            a.createdby = request.user
            a.save()
        else:
            messages.success(request, leadform.errors)
            return render(request, 'lead/addlead.html', context)

        messages.success(request, 'Lead added Successfully ')
        return HttpResponseRedirect(reverse('marketing:leadlist'))
    else:
        leadform = LeadForm()
        context['leadform'] = leadform
        return render(request, 'lead/addlead.html', context)


@login_required(login_url='/login/')
@accessview
def leadedit(request, id=None):
    context = {}
    instance = get_object_or_404(Lead, id=id)
    if request.method == 'POST':
        leadform = LeadForm(request.POST, instance=instance)
        context['leadform'] = leadform
        if leadform.is_valid():
            a = leadform.save(commit=False)
            a.editedby = request.user
            a.save()
        else:
            messages.success(request, leadform.errors)
            return render(request, 'lead/editlead.html', context)

        messages.success(request, 'Lead added Successfully ')
        return HttpResponseRedirect(reverse('marketing:leadedit', kwargs={'id': a.id}))
    else:
        leadform = LeadForm(instance=instance)
        context['leadform'] = leadform
        return render(request, 'lead/editlead.html', context)


@login_required(login_url='/login/')
@accessview
def routelist(request):
    route_list = Route.objects.filter()
    myFilter = RouteFilter(request.GET, route_list)
    route_list = myFilter.qs

    page = request.GET.get('page', 1)
    paginator = Paginator(route_list, 100)
    try:
        routes = paginator.page(page)
    except PageNotAnInteger:
        routes = paginator.page(1)
    except EmptyPage:
        routes = paginator.page(paginator.num_pages)
    return render(request, 'route/routelist.html', {'routes': routes, 'myFilter': myFilter})


@login_required(login_url='/login/')
@accessview
def routeadd(request):
    context = {}
    if request.method == 'POST':
        routeform = RouteForm(request.POST)
        context['routeform'] = routeform
        if routeform.is_valid():
            a = routeform.save(commit=False)
            a.createdby = request.user
            a.save()
        else:
            messages.success(request, routeform.errors)
            return render(request, 'route/addroute.html', context)

        messages.success(request, 'Route Created Successfully ')
        return HttpResponseRedirect(reverse('marketing:routeedit', kwargs={'id': a.id}))
    else:
        routeform = RouteForm()
        context['routeform'] = routeform
        return render(request, 'route/addroute.html', context)


@login_required(login_url='/login/')
@accessview
def routeedit(request, id=None):
    context = {}
    route = get_object_or_404(Route, id=id)
    context['route'] = route
    routecustomerformset = inlineformset_factory(Route, RouteCustomer, fk_name='route',
                                                 form=RouteCustomerForm, extra=2)
    print('marketing persong',route.marketing_person)
    if request.method == 'POST':
        routeform = RouteForm(request.POST, instance=route)
        routecustomerform = routecustomerformset(request.POST, prefix='routecustomerformset',
                                                 instance=route, form_kwargs={'routeuser': route.marketing_person})
        context['routeform'] = routeform
        context['routecustomerform'] = routecustomerform

        if routeform.is_valid() and routecustomerform.is_valid():
            a = routeform.save(commit=False)
            a.createdby = request.user
            a.save()
            routecustomerform.save()
            routeform = RouteForm(instance=route)
            context['routeform'] = routeform
            routecustomerform = routecustomerformset(prefix='routecustomerformset',
                                                     instance=route,form_kwargs={'routeuser': route.marketing_person})
            context['routecustomerform'] = routecustomerform
        else:
            context['routeform'] = routeform
            context['routecustomerform'] = routecustomerform
            messages.success(request, routeform.errors)
            messages.success(request, routecustomerform.errors)
            return render(request, 'route/editroute.html', context)

        messages.success(request, 'Route Saved ')
        return render(request, 'route/editroute.html', context)
    else:
        routeform = RouteForm(instance=route, )
        context['routeform'] = routeform
        routecustomerform = routecustomerformset(prefix='routecustomerformset',
                                                 instance=route, form_kwargs={'routeuser': route.marketing_person})
        context['routecustomerform'] = routecustomerform
        return render(request, 'route/editroute.html', context)


@login_required(login_url='/login/')
@accessview
def visitfeedback(request, id=None):
    context = {}
    route = get_object_or_404(Route, id=id)
    context['route'] = route
    routecustomerformset = inlineformset_factory(Route, RouteCustomer, fk_name='route',
                                                 form=RouteFeedbackForm, extra=0
                                                 )
    if request.method == 'POST':
        routeform = RouteForm(request.POST, instance=route)
        routecustomerform = routecustomerformset(request.POST, prefix='routecustomerformset',
                                                 instance=route)
        context['routeform'] = routeform
        context['routecustomerform'] = routecustomerform

        if routeform.is_valid() and routecustomerform.is_valid():
            a = routeform.save(commit=False)
            a.createdby = request.user
            a.save()
            routecustomerform.save()
            routeform = RouteForm(instance=route)
            context['routeform'] = routeform
            routecustomerform = routecustomerformset(prefix='routecustomerformset',
                                                     instance=route)
            context['routecustomerform'] = routecustomerform
        else:
            context['routeform'] = routeform
            context['routecustomerform'] = routecustomerform
            messages.success(request, routeform.errors)
            messages.success(request, routecustomerform.errors)
            return render(request, 'route/visitreview.html', context)

        messages.success(request, 'Route Saved ')
        return render(request, 'route/visitreview.html', context)
    else:
        routeform = RouteForm(instance=route)
        context['routeform'] = routeform
        routecustomerform = routecustomerformset(prefix='routecustomerformset',
                                                 instance=route)
        context['routecustomerform'] = routecustomerform
        return render(request, 'route/visitreview.html', context)


@login_required(login_url='/login/')
@accessview
def bunchadd(request):
    context = {}

    bunchform = BunchForm(request.POST or None)
    context['bunchform'] = bunchform
    if request.method == 'POST':

        if bunchform.is_valid():
            bunch = bunchform.save(commit=False)
            bunch.createdby = request.user
            bunch.save()
            bunchform.save_m2m()
            return HttpResponseRedirect(reverse('marketing:bunchedit', kwargs={'id': bunch.id}))
        else:
            print(bunchform.errors)
            context['bunchform'] = bunchform
            return render(request, 'bunch/bunchadd.html', context)

    return render(request, 'bunch/bunchadd.html', context)


@login_required(login_url='/login/')
@accessview
def bunchedit(request, id=None):
    context = {}
    bunchinstance = get_object_or_404(Bunch, id=id)

    bunchform = BunchForm(request.POST or None, instance=bunchinstance)
    context['bunchform'] = bunchform
    if request.method == 'POST':

        if bunchform.is_valid():
            bunchform.save()
            return HttpResponseRedirect(reverse('marketing:bunchedit', kwargs={'id': id}))
        else:
            print(bunchform.errors)
            context['bunchform'] = bunchform
            return render(request, 'bunch/bunchadd.html', context)

    return render(request, 'bunch/bunchedit.html', context)


@login_required(login_url='/login/')
@accessview
def bunchlist(request):
    bunch_list = Bunch.objects.filter()
    myFilter = BunchFilter(request.GET, bunch_list)
    bunch_list = myFilter.qs

    page = request.GET.get('page', 1)
    paginator = Paginator(bunch_list, 100)
    try:
        bunches = paginator.page(page)
    except PageNotAnInteger:
        bunches = paginator.page(1)
    except EmptyPage:
        bunches = paginator.page(paginator.num_pages)
    return render(request, 'bunch/bunchlist.html', {'bunches': bunches, 'myFilter': myFilter})
