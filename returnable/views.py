from django.forms import inlineformset_factory
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from customer.models import Address
from myproject.access import accessview
from .filters import ReturnableFilter, ChallanItemFilter, ReceivedChallanFilter
from .forms import ReturnableForm, ChallanItemForm, ReceivedChallanForm, ReceivedItemForm
from .models import Returnable, ChallanItem, ReceivedChallan, ReceivedItem
from django.urls import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger



@login_required(login_url='/login/')
@accessview
def returnablelist(request):
    params = request.GET.copy()
    params.pop('page', None)
    param = ('&' + params.urlencode()) if params else ''

    q = request.GET.get('q', None)
    if request.user.username in ["khadimhusen", "firoj", "admin", "ashraf"]:
        returnable_list = Returnable.objects.filter(state=q) if q else Returnable.objects.all()
    else:
        returnable_list = Returnable.objects.filter(state=q, createdby=request.user) if q else Returnable.objects.filter(createdby=request.user)

    myFilter = ReturnableFilter(request.GET, queryset=returnable_list)
    returnable_list = myFilter.qs.select_related('party_name', 'createdby')

    page = request.GET.get('page', 1)
    paginator = Paginator(returnable_list, 100)
    try:
        returnable_list = paginator.page(page)
    except PageNotAnInteger:
        returnable_list = paginator.page(1)
    except EmptyPage:
        returnable_list = paginator.page(paginator.num_pages)

    return render(request, 'returnable/returnablelist.html', {
        'returnable_list': returnable_list,
        'myFilter': myFilter,
        'param': param
    })

@login_required(login_url='/login/')
@accessview
def challanitemlist(request):
    params = request.GET.copy()
    params.pop('page', None)
    param = ('&' + params.urlencode()) if params else ''

    if request.user.username in ["khadimhusen", "firoj", "admin", "ashraf"]:
        challanitem_list = ChallanItem.objects.all()
    else:
        challanitem_list = ChallanItem.objects.filter(returnable__createdby=request.user)

    myFilter = ChallanItemFilter(request.GET, queryset=challanitem_list)
    challanitem_list = myFilter.qs.select_related(
        'returnable__party_name', 'unit'
    )

    page = request.GET.get('page', 1)
    paginator = Paginator(challanitem_list, 100)
    try:
        challanitem_list = paginator.page(page)
    except PageNotAnInteger:
        challanitem_list = paginator.page(1)
    except EmptyPage:
        challanitem_list = paginator.page(paginator.num_pages)

    return render(request, 'returnable/challanitemlist.html', {
        'challanitem_list': challanitem_list,
        'myFilter': myFilter,
        'param': param
    })


@login_required(login_url='/login/')
@accessview
def returnablenew(request):
    context = {}
    if request.method == 'POST':

        returnable_form = ReturnableForm(request.POST)
        context['returnable_form'] = returnable_form
        if returnable_form.is_valid():
            returnableform = returnable_form.save(commit=False)
            returnableform.createdby = request.user
            returnableform.status = "Pending"
            returnableform.save()
            return HttpResponseRedirect(reverse('returnable:returnableedit', kwargs={'id': returnableform.id}))
        else:
            print(returnable_form.errors)
            return render(request, 'returnable/returnablenew.html', context)
    else:
        returnable_form = ReturnableForm()
        context['returnable_form'] = returnable_form
        return render(request, 'returnable/returnablenew.html', context)


@login_required(login_url='/login/')
@accessview
def returnableedit(request, id=None):
    context = {}
    returnablechallan = get_object_or_404(Returnable, id=id)
    returnable_form = ReturnableForm(request.POST or None, instance=returnablechallan)
    challanformset = inlineformset_factory(Returnable, ChallanItem, ChallanItemForm, extra=12, max_num=12, can_delete=True)
    challanitemforms = challanformset(request.POST or None, prefix="challanitemform", instance=returnablechallan)

    if request.method == 'POST':
        context['returnable_form'] = returnable_form
        context['challanitemforms'] = challanitemforms
        if returnable_form.is_valid() and challanitemforms.is_valid():
            try:
                print("both form are valid")
                returnable_form.save(commit=False)
                returnable_form.editedby = request.user
                returnable_form.save()
                challanitemforms.save()
                return HttpResponseRedirect(reverse('returnable:returnableedit', kwargs={'id': id}))
            except:

                messages.warning(request, 'something gone wrong')
                print("returnable_form", returnable_form.errors)
                print("challanitemforms", challanitemforms.errors)
                return render(request, 'returnable/returnableedit.html', context)
        else:
            print("returnable_form", returnable_form.errors)
            print("challanitemforms", challanitemforms.errors)
            return render(request, 'returnable/returnableedit.html', context)

    else:

        context['returnable_form'] = returnable_form
        context['challanitemforms'] = challanitemforms
        return render(request, 'returnable/returnableedit.html', context)


@login_required(login_url='/login/')
@accessview
def returnabledetail(request,id=None):
    rc = get_object_or_404(Returnable, id=id)
    context={"rc":rc}
    return render(request, 'returnable/returnabledetail.html', context)


@login_required(login_url='/login/')
def load_address(request):
    customer_id = request.GET.get('customer')
    addresses = Address.objects.filter(customer_id=customer_id).order_by('addname')
    return render(request, 'customer/address_dropdown_list_options.html', {'addresses': addresses})


@login_required(login_url='/login/')
def receivedchallannew(request):
    context = {}
    if request.method == 'POST':

        rc_form = ReceivedChallanForm(request.POST)
        context['rc_form'] = rc_form
        if rc_form.is_valid():
            rc = rc_form.save(commit=False)
            rc.createdby = request.user
            rc.save()
            return HttpResponseRedirect(reverse('returnable:r_c_edit', kwargs={'id': rc.id}))
        else:
            return render(request, 'received/new.html', context)
    else:
        rc = ReceivedChallanForm()
        context['rc_form'] = rc
        return render(request, 'received/new.html', context)



RCItemFormSet = inlineformset_factory(
    ReceivedChallan, ReceivedItem, ReceivedItemForm,
    extra=3, max_num=10, can_delete=True
)

@login_required(login_url='/login/')
@accessview
def r_c_edit(request, id=None):
    rc = get_object_or_404(ReceivedChallan, id=id)
    rc_form = ReceivedChallanForm(request.POST or None, instance=rc)

    rc_item_form = RCItemFormSet(
        request.POST or None,
        prefix="challanitemform",
        instance=rc,
        form_kwargs={'rc_instance': rc} )


    context = {
        'rc_form': rc_form,
        'rc_item_form': rc_item_form,
    }

    if request.method == 'POST':
        if rc_form.is_valid() and rc_item_form.is_valid():
            try:
                rc_form.save()
                rc_item_form.save()
                messages.warning(request, 'save ok')

                return HttpResponseRedirect(reverse('returnable:r_c_edit', kwargs={'id': id}))
            except Exception as e:
                print(f"Error: {e}")
                messages.warning(request, 'Something went wrong. Please try again.')
        else:
            print("rc_form errors:", rc_form.errors)
            print("rc_item_form errors:", rc_item_form.errors)

    return render(request, 'received/receivededit.html', context)

@login_required(login_url='/login/')
@accessview
def receivedlist(request):
    params = request.GET.copy()
    params.pop('page', None)
    param = ('&' + params.urlencode()) if params else ''

    q = request.GET.get('q', None)
    if request.user.username in ["khadimhusen", "firoj","zaid"]:
        receivedchallan_list = ReceivedChallan.objects.filter(state=q) if q else ReceivedChallan.objects.all()
    else:
        receivedchallan_list = ReceivedChallan.objects.filter(state=q, createdby=request.user) if q else ReceivedChallan.objects.filter(createdby=request.user)

    myFilter = ReceivedChallanFilter(request.GET, queryset=receivedchallan_list)
    receivedchallan_list = myFilter.qs.select_related('party_name', 'createdby')

    page = request.GET.get('page', 1)
    paginator = Paginator(receivedchallan_list, 100)
    try:
        receivedchallan_list = paginator.page(page)
    except PageNotAnInteger:
        receivedchallan_list = paginator.page(1)
    except EmptyPage:
        receivedchallan_list = paginator.page(paginator.num_pages)

    return render(request, 'received/receivedchallanlist.html', {
        'returnable_list': receivedchallan_list,
        'myFilter': myFilter,
        'param': param
    })
