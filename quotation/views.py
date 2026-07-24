from django.forms import inlineformset_factory
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.db.models import F
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from datetime import datetime

from employee.models import Department
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
    context = {}
    if not Department.objects.filter(department_name="all_quote_list", user=request.user).exists():

        param = request.get_full_path().replace(request.path, "")
        q = request.GET.get('deleted', None)
        if q != None:
            quot_list = Quotation.objects.filter(is_deleted=q, createdby=request.user)
        else:
            quot_list = Quotation.objects.filter(is_deleted=False, createdby=request.user)
    else:
        param = request.get_full_path().replace(request.path, "")
        q = request.GET.get('deleted', None)
        if q != None:
            quot_list = Quotation.objects.filter(is_deleted=q)
        else:
            quot_list = Quotation.objects.filter(is_deleted=False)

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

    from task.models import Task

    if request.session.pop('show_pending_tasks', False):
        pending_tasks = Task.objects.filter(
            task_alloted_to=request.user,
            is_closed=False
        ).select_related('createdby').order_by('target_date')[:10]

        context['pending_tasks_popup'] = pending_tasks if pending_tasks.exists() else None

    context['quo'] = quo
    context['myFilter'] = myFilter
    context['param'] = param

    return render(request, "quotation/list.html", context)


def materialjson(request):
    data = list(MaterialRate.objects.values("density", "rate", "solid", "material"))
    return JsonResponse(data, safe=False)


def getstructurejson(request, ply="3ply"):
    data = list(MaterialStructure.objects.filter(predefined__structure=ply).values(film=F("material__material"),
                                                                                   mic=F('micron')))
    return JsonResponse(data, safe=False)


@csrf_exempt
def getquotationjson(request, id=None):
    quote = Quotation.objects.filter(id=id or 1)
    serializer = QuotationSerializer(quote)
    # data = list(Quotation.objects.filter(id=id or 1).values())

    return JsonResponse(serializer.data, safe=False)


@login_required(login_url='/login/')
@accessview
def editquote(request, id=None):
    context = {}

    quote = get_object_or_404(Quotation, id=id)
    quoteitemformset = inlineformset_factory(Quotation, QuotationItem, QuoteItemForm, extra=12, max_num=20,
                                             can_delete=True)
    additiontermformset = inlineformset_factory(Quotation, AdditionTerm, AdditionTermForm, extra=3, max_num=20,
                                                can_delete=True)

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
            except:
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

            if  Department.objects.filter(department_name="can_approve_quote", user=request.user).exists():
                mainform = QuotationForm(instance=quote)
                quoteitemform = quoteitemformset(prefix="quoteitemform", instance=quote)
                additiontermform = additiontermformset(prefix="additiontermform", instance=quote)
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
def detailquote(request, id=None):
    context = {}
    quote = get_object_or_404(Quotation, id=id)
    context["quoteapprovalform"] = QuoteApprovalForm(instance=quote, initial={'approvedby': request.user})
    context["quote"] = quote
    return render(request, "quotation/quotedetail.html", context)


def quotepdf(request, id=None):
    context = {}
    quote = get_object_or_404(Quotation, id=id)
    context["quoteapprovalform"] = QuoteApprovalForm(instance=quote, initial={'approvedby': request.user})
    context["quote"] = quote
    return render(request, "quotation/quotedetail.html", context)


@login_required(login_url='/login/')
@accessview
def quoteapproval(request, id=None):
    context = {}
    quote = get_object_or_404(Quotation, id=id)
    if request.method == "POST" and request.user:
        form = QuoteApprovalForm(request.POST, instance=quote)
        context["quoteapprovalform"] = form
        if form.is_valid():
            forminstance = form.save(commit=False)
            forminstance.approvedby = request.user
            forminstance.approved = datetime.now()
            forminstance.save()
            messages.success(request, "Quotation is Approved")
            return HttpResponseRedirect(reverse('quotation:quotationdetail', kwargs={'id': quote.id}))
    return HttpResponseRedirect(reverse('quotation:quotationdetail', kwargs={'id': quote.id}))


@login_required(login_url='/login/')
@accessview
def clonequote(request, id=None):
    context = {}
    quote = get_object_or_404(Quotation, id=id)
    quoteitemformset = inlineformset_factory(Quotation, QuotationItem, QuoteItemForm, extra=12, max_num=20,
                                             can_delete=True)
    additiontermformset = inlineformset_factory(Quotation, AdditionTerm, AdditionTermForm, extra=3, max_num=20,
                                                can_delete=True)

    if request.method == 'POST':
        mainform = QuotationForm(request.POST)
        quoteitemform = quoteitemformset(request.POST or None, prefix="quoteitemform")
        additiontermform = additiontermformset(request.POST or None, prefix="additiontermform")
        context['mainform'] = mainform
        context['quoteitemform'] = quoteitemform
        context['additiontermform'] = additiontermform
        if mainform.is_valid() and quoteitemform.is_valid() and additiontermform.is_valid():
            try:
                mainquote = mainform.save(commit=False)

                mainquote.createdby = request.user
                mainquote.save()
                quote = get_object_or_404(Quotation, id=mainquote.id)
                print("quote -", quote)
                for i in quoteitemform:
                    print("quoteform id:- ", i.cleaned_data['id'])
                #
                # q=quoteitemform.save(commit=False)
                # q.quote=quote
                # q.save()
                # a=additiontermform.save(commit=False)
                # a.quote=quote
                # a.save()
                return HttpResponseRedirect(reverse('quotation:quotationdetail', kwargs={'id': mainquote.id}))
            except:
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
        mainform = QuotationForm(instance=quote)
        quoteitemform = quoteitemformset(prefix="quoteitemform", instance=quote)
        additiontermform = additiontermformset(prefix="additiontermform", instance=quote)
        context['mainform'] = mainform
        context['quoteitemform'] = quoteitemform
        context['additiontermform'] = additiontermform
        return render(request, 'quotation/editquote.html', context)


from django.db import transaction


@login_required(login_url='/login/')
@accessview
def copyquote(request, id=None):
    original_quote = get_object_or_404(Quotation, id=id)

    # Server-side verification
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return HttpResponseRedirect(reverse('quotation:quotationdetail', kwargs={'id': id}))

    confirm_id = request.POST.get('confirm_id', '').strip()
    if confirm_id != str(id):
        messages.error(request, 'Quote ID confirmation did not match. Copy cancelled.')
        return HttpResponseRedirect(reverse('quotation:quotationdetail', kwargs={'id': id}))

    # ... rest of your copy logic
    try:
        with transaction.atomic():
            original_items = list(original_quote.quotationitems.all())
            original_terms = list(original_quote.quote_term.all())

            new_quote = original_quote
            new_quote.pk = None
            new_quote.approvedby = None
            new_quote.approved = None
            new_quote.status = "Pending"
            new_quote.createdby = request.user
            new_quote.editedby = request.user
            new_quote.save()

            new_quote.quote_term.set(original_terms)

            for item in original_items:
                item.pk = None
                item.quote = new_quote
                item.createdby = request.user
                item.editedby = request.user
                item.save()

        messages.success(request, 'Quotation copied successfully.')
        return HttpResponseRedirect(reverse('quotation:editquote', kwargs={'id': new_quote.id}))

    except Exception as e:
        messages.error(request, f'Error copying quotation: {str(e)}')
        return HttpResponseRedirect(reverse('quotation:quotationdetail', kwargs={'id': id}))
