from django.shortcuts import render, get_object_or_404, redirect
from .models import Customer, Address, Person
from django.http import HttpResponseRedirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from .forms import CustomerForm, AddressForm, PersonForm
from django.urls import reverse
from django.forms import modelformset_factory, inlineformset_factory
from myproject.access import accessview
from django.contrib import messages
from order.models import Job
from order.filters import JobFilter
from .filters import CustomerFilter, CustomerAddressFilter


@login_required(login_url='/login/')
@accessview
def customerlist(request):

    q = request.GET.get('q', None)
    if q != None:
        cust_list = Address.objects.filter(customer__active=q).order_by("-customer__id")
    else:
        cust_list = Address.objects.all().order_by("-customer__id")

    myFilter = CustomerAddressFilter(request.GET, cust_list)
    cust_list = myFilter.qs
    totalcount = cust_list.count()

    page = request.GET.get('page', 1)
    paginator = Paginator(cust_list, 1000)

    try:
        custs = paginator.page(page)
    except PageNotAnInteger:
        custs = paginator.page(1)
    except EmptyPage:
        custs = paginator.page(paginator.num_pages)
    return render(request, 'customer/customer_list.html', {'custs': custs, 'q': q, 'total': totalcount,'myFilter':myFilter})


@login_required(login_url='/login/')
@accessview
def customerdetail(request, id):
    customer = get_object_or_404(Customer, id=id)
    context = {}
    context['customer'] = customer

    job_list=Job.objects.filter(joborder__customer= customer)

    myFilter = JobFilter(request.GET, job_list)
    job_list = myFilter.qs
    totalcount = job_list.count()

    page = request.GET.get('page', 1)
    paginator = Paginator(job_list, 20)
    try:
        jobs = paginator.page(page)
    except PageNotAnInteger:
        jobs = paginator.page(1)
    except EmptyPage:
        jobs = paginator.page(paginator.num_pages)

    context['jobs'] = jobs
    context['myFilter']=myFilter
    context['total']=totalcount

    return render(request, 'customer/customer_detail.html', context)

@login_required(login_url='/login/')
@accessview
def customeradd(request):
    context = {}
    if request.method == 'POST':
        cust_form = CustomerForm(request.POST)
        context['cust_form'] = cust_form
        if cust_form.is_valid():
            custsave = cust_form.save(commit=False)
            custsave.createdby=request.user
            custsave.save()

            messages.success(request, f'New Customer: { custsave.name} Added successfuly. Please add other detail')
            return HttpResponseRedirect(reverse('customer:customerdetailedit', kwargs={'id': custsave.id}))
        else:
            return render(request, 'customer/add.html', context)
    else:
        cust_form = CustomerForm()
        context['cust_form'] = cust_form
        return render(request, 'customer/add.html', context)


@login_required(login_url='/login/')
@accessview
def customeredit(request, id=None):
    customer = get_object_or_404(Customer, id=id)
    if request.method == 'POST':
        cust = CustomerForm(request.POST, instance=customer)
        if cust.is_valid():
            custsave=cust.save(commit=False)
            custsave.editedby=request.user
            custsave.save()
            return HttpResponseRedirect(reverse('customer:customerlist'))
        else:
            return render(request, 'customer/edit.html', {'cust': cust})
    else:
        cust = CustomerForm(instance=customer)
        return render(request, 'customer/edit.html', {'cust': cust})


@login_required(login_url='/login/')
@accessview
def customerdetailadd(request):
    context = {}
    addressformset = modelformset_factory(Address, form=AddressForm, extra=2, )
    personformset = modelformset_factory(Person, form=PersonForm, extra=2)
    if request.method == 'POST':
        cust_form = CustomerForm(request.POST)
        formset1 = addressformset(request.POST or None, prefix='addressformeset')
        formset2 = personformset(request.POST or None, prefix='personformeset')
        context['cust_form'] = cust_form
        context['address_forms'] = formset1
        context['person_forms'] = formset2
        if cust_form.is_valid() and formset1.is_valid() and formset2.is_valid():
            customer = cust_form.save(commit=False)
            customer.createdby=request.user
            customer.save()
            for f in formset1:
                if f.cleaned_data:
                    if f.cleaned_data['id'] is None:
                        address = f.save(commit=False)
                        address.customer = customer
                        address.createdby=request.user
                        address.save()
            for f in formset2:
                if f.cleaned_data:
                    if f.cleaned_data['id'] is None:
                        person = f.save(commit=False)
                        person.customer = customer
                        person.createdby=request.user
                        person.save()
            messages.success(request, f'New Customer: { customer.name} Added ')
            if request.GET.get('next', None):
                return redirect(request.GET['next'])
            return HttpResponseRedirect(reverse('customer:customerlist'))
        else:
            return render(request, 'customer/new_customer.html', context)
    else:
        cust_form = CustomerForm()
        context['cust_form'] = cust_form
        context['address_forms'] = addressformset(queryset=Address.objects.none(), prefix='addressformeset')
        context['person_forms'] = personformset(queryset=Person.objects.none(), prefix='personformeset')
        return render(request, 'customer/new_customer.html', context)


@login_required(login_url='/login/')
@accessview
def customerdetailedit(request, id=None):
    context = {}
    customer = get_object_or_404(Customer, id=id)
    addressformset = inlineformset_factory(Customer, Address, fields=('addname', 'add1', 'add2', 'pincode', 'phone',),
                                           extra=1)
    personformset = inlineformset_factory(Customer, Person, fields=('name', 'designation', 'mobile', 'email',), extra=1)
    if request.method == 'POST':
        cust = CustomerForm(request.POST, instance=customer)
        formset1 = addressformset(request.POST, prefix='addressformset', instance=customer)
        formset2 = personformset(request.POST, prefix='personformset', instance=customer)
        context['cust_form'] = cust
        context['address_forms'] = formset1
        context['person_forms'] = formset2
        if cust.is_valid() and formset1.is_valid() and formset2.is_valid():
            cust.save(commit=False)
            customer.editedby=request.user
            cust.save()
            formset1.editedby=request.user
            formset1.save()
            formset2.save()
            return HttpResponseRedirect(reverse('customer:customerlist'))
        else:
            return render(request, 'customer/edit_customer.html', context)
    else:
        userlist = ["admin","khadimhusen","firoj","sarfaraj",customer.createdby.username]
        if request.user.username in userlist:
            cust = CustomerForm(instance=customer)
            formset1 = addressformset(instance=customer, prefix='addressformset')
            formser2 = personformset(instance=customer, prefix='personformset')
            context['cust_form'] = cust
            context['address_forms'] = formset1
            context['person_forms'] = formser2
            return render(request, 'customer/edit_customer.html', context)
        else:
            messages.success(request, 'You are not Authorise to change detail of this customer. ' )
            return HttpResponseRedirect(reverse('customer:customerlist'))


