from django.forms import inlineformset_factory
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.db.models import F
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from datetime import datetime

from .filters import QuotationFilter
from .forms import QuotationForm, QuoteItemForm, QuoteApprovalForm, AdditionTermForm
from .models import Quotation, QuotationItem, MaterialRate, Term, AdditionTerm, PreDefinedMaterial, MaterialStructure
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from myproject.access import accessview, forceview
from .serializers import QuotationSerializer
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


@login_required(login_url='/login/')
@forceview
@accessview
def costing(request):
    context = {}
    context['material'] = MaterialRate.objects.all()
    return render(request, "quotation/costing.html", context)




@login_required(login_url='/login/')
@accessview
def addquotation(request):
    context = {}
    quotation_form = QuotationForm(request.POST or None)
    context['quotation_form'] = quotation_form
    if request.method == "POST":

        if quotation_form.is_valid():
            quot_form = quotation_form.save(commit=False)
            quot_form.createdby = request.user
            quot_form.save()
            quotation_form.save_m2m()
            return HttpResponseRedirect(reverse('quotation:editquote', kwargs={'id': quot_form.id}))
        else:
            context['quotation_form'] = quotation_form
    return render(request, "quotation/addquotation.html", context)


@login_required(login_url='/login/')
@accessview
def quotationlist(request):


    if request.user.username not in ["khadimhusen","firoj","admin"]:

        param = request.get_full_path().replace(request.path, "")
        q = request.GET.get('deleted', None)
        if q != None:
            quot_list = Quotation.objects.filter(is_deleted=q,createdby = request.user)
        else:
            quot_list = Quotation.objects.filter(is_deleted=False,createdby = request.user)
    else:
        param = request.get_full_path().replace(request.path, "")
        q = request.GET.get('deleted', None)
        if q != None:
            quot_list = Quotation.objects.filter(is_deleted =q)
        else:
            quot_list = Quotation.objects.filter(is_deleted =False)

    myFilter = QuotationFilter(request.GET, quot_list)
    quot_list = myFilter.qs.select_related()

    page = request.GET.get('page', 1)
    paginator = Paginator(quot_list, 100)

    try:
        quo = paginator.page(page)
    except PageNotAnInteger:
        quo = paginator.page(1)
    except EmptyPage:
        quo = paginator.page(paginator.num_pages)

    return render(request, "quotation/list.html",
                  {"quo": quo, "myFilter": myFilter, "param": param})


def materialjson(request):
    data = list(MaterialRate.objects.values("density","rate","solid","material"))
    return JsonResponse(data,safe=False)

def getstructurejson(request,ply="3ply"):
    data = list(MaterialStructure.objects.filter(predefined__structure=ply).values(film=F("material__material"),mic=F('micron')))
    return JsonResponse(data,safe=False)

@csrf_exempt
def getquotationjson(request,id=None):
    quote=Quotation.objects.filter(id=id or 1)
    serializer=QuotationSerializer(quote)
    # data = list(Quotation.objects.filter(id=id or 1).values())

    return JsonResponse(serializer.data, safe=False)

@login_required(login_url='/login/')
@accessview
def editquote(request, id=None):
    context = {}

    quote = get_object_or_404(Quotation, id=id)
    quoteitemformset = inlineformset_factory(Quotation, QuotationItem, QuoteItemForm, extra=12, max_num=12, can_delete=True)
    additiontermformset = inlineformset_factory(Quotation, AdditionTerm, AdditionTermForm, extra=3, max_num=12, can_delete=True)

    if request.method == 'POST':
        mainform = QuotationForm(request.POST, instance=quote)
        quoteitemform = quoteitemformset(request.POST or None, prefix="quoteitemform", instance=quote)
        additiontermform = additiontermformset(request.POST or None, prefix="additiontermform", instance=quote)
        context['mainform'] = mainform
        context['quoteitemform'] = quoteitemform
        context['additiontermform'] = additiontermform
        if mainform.is_valid() and quoteitemform.is_valid() and additiontermform.is_valid():
            try:
                mainform.save(commit=False)
                mainform.editedby = request.user
                mainform.save()
                quoteitemform.save()
                additiontermform.save()
                return HttpResponseRedirect(reverse('quotation:quotationdetail', kwargs={'id': id}))
            except :
                messages.warning(request, 'Something gone wrong')
                print("mainform", mainform.errors)
                print("quoteitemform", quoteitemform.errors)
                print("additiontermform", additiontermform.errors)
                print("quoteitemform non form ")
                return render(request, 'quotation/editquote.html', context)
        else:
            print("mainform :-", mainform.errors)
            print("quoteitemforms :-", quoteitemform.errors)
            print("additiontermform :-", additiontermform.errors)
            return render(request, 'quotation/editquote.html', context)
    else:

        if quote.approvedby:
            if request.user.username =="firoj" or request.user.username=="khadimhusen":
                mainform = QuotationForm( instance=quote)
                quoteitemform = quoteitemformset(prefix="quoteitemform", instance=quote)
                additiontermform = additiontermformset( prefix="additiontermform", instance=quote)
                context['mainform'] = mainform
                context['quoteitemform'] = quoteitemform
                context['additiontermform'] = additiontermform
                return render(request, 'quotation/editquote.html', context)
            else:
                return HttpResponseRedirect(reverse('quotation:quotationdetail', kwargs={'id': id}))
        else:
            mainform = QuotationForm(instance=quote)
            quoteitemform = quoteitemformset(prefix="quoteitemform", instance=quote)
            additiontermform = additiontermformset(prefix="additiontermform", instance=quote)
            context['mainform'] = mainform
            context['quoteitemform'] = quoteitemform
            context['additiontermform'] = additiontermform
            return render(request, 'quotation/editquote.html', context)

@login_required(login_url='/login/')
@accessview
def detailquote (request,id=None):
    context = {}
    quote = get_object_or_404(Quotation, id=id)
    context["quoteapprovalform"] = QuoteApprovalForm(instance=quote,initial={'approvedby': request.user})
    context["quote"]=quote
    return render(request, "quotation/quotedetail.html",context)

def quotepdf(request,id=None):
    context = {}
    quote = get_object_or_404(Quotation, id=id)
    context["quoteapprovalform"] = QuoteApprovalForm(instance=quote,initial={'approvedby': request.user})
    context["quote"]=quote
    return render(request, "quotation/quotedetail.html",context)


@login_required(login_url='/login/')
@accessview
def quoteapproval(request,id=None):
    context = {}
    quote = get_object_or_404(Quotation, id=id)
    if request.method == "POST" and request.user:
        form = QuoteApprovalForm(request.POST, instance=quote)
        context["quoteapprovalform"]=form
        if form.is_valid():
            forminstance = form.save(commit=False)
            forminstance.approvedby = request.user
            forminstance.approved = datetime.now()
            forminstance.save()
            messages.success(request,"Quotation is Approved")
            return HttpResponseRedirect(reverse('quotation:quotationdetail', kwargs={'id':quote.id}))
    return HttpResponseRedirect(reverse('quotation:quotationdetail', kwargs={'id':quote.id}))


@login_required(login_url='/login/')
@accessview
def clonequote(request, id=None):
    context = {}
    quote = get_object_or_404(Quotation, id=id)
    quoteitemformset = inlineformset_factory(Quotation, QuotationItem, QuoteItemForm, extra=12, max_num=2, can_delete=True)
    additiontermformset = inlineformset_factory(Quotation, AdditionTerm, AdditionTermForm, extra=3, max_num=2, can_delete=True)

    if request.method == 'POST':
        mainform = QuotationForm(request.POST)
        quoteitemform = quoteitemformset(request.POST or None, prefix="quoteitemform")
        additiontermform = additiontermformset(request.POST or None, prefix="additiontermform")
        context['mainform'] = mainform
        context['quoteitemform'] = quoteitemform
        context['additiontermform'] = additiontermform
        if mainform.is_valid() and quoteitemform.is_valid() and additiontermform.is_valid():
            try:
                mainquote=mainform.save(commit=False)

                mainquote.createdby = request.user
                mainquote.save()
                quote = get_object_or_404(Quotation, id=mainquote.id)
                print("quote -",quote)
                for i in quoteitemform:
                    print("quoteform id:- ",i.cleaned_data['id'])
                #
                # q=quoteitemform.save(commit=False)
                # q.quote=quote
                # q.save()
                # a=additiontermform.save(commit=False)
                # a.quote=quote
                # a.save()
                return HttpResponseRedirect(reverse('quotation:quotationdetail', kwargs={'id': mainquote.id}))
            except :
                messages.warning(request, 'Something gone wrong')
                print("mainform", mainform.errors)
                print("quoteitemform", quoteitemform.errors)
                print("additiontermform", additiontermform.errors)
                print("quoteitemform non form ")
                return render(request, 'quotation/editquote.html', context)
        else:
            print("mainform :-", mainform.errors)
            print("quoteitemforms :-", quoteitemform.errors)
            print("additiontermform :-", additiontermform.errors)
            return render(request, 'quotation/editquote.html', context)
    else:
        mainform = QuotationForm( instance=quote)
        quoteitemform = quoteitemformset(prefix="quoteitemform", instance=quote)
        additiontermform = additiontermformset( prefix="additiontermform", instance=quote)
        context['mainform'] = mainform
        context['quoteitemform'] = quoteitemform
        context['additiontermform'] = additiontermform
        return render(request, 'quotation/editquote.html', context)
