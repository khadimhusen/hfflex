from django.contrib import messages
from django.db.models import Sum, F
from django.urls import reverse
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.forms import generic_inlineformset_factory
from django.forms import inlineformset_factory, modelform_factory
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import datetime

from material.models import Material
from .models import (Inward, Stockdetail, ProdReport, ProdInput, ProdPerson, JobMaterialStatus,
                     DispatchRegister, ProdProblem, ProblemTag, OtherDispatchItem)

from order.models import JobProcess, JobMaterial, Job
from myproject.access import accessview
from .forms import (InwardForm, InwardMaterialForm, ProdReportForm, NewProdReportForm, ProdOutputForm,
                    ProdOutputAddForm, ProdInputForm, JobMaterialStatusForm, ProdInputEditForm,
                    DispatchForm, JobAllotementForm, StockMaterailAlloteForm, AddPersonForm,
                    StockMaterailUsedForm, ProdInputBlankForm, DispatchNewForm, AddProblemForm, StockMaterailEditForm,
                    DispatchApprovalForm, Jobmaterialtoroder, AddJobQcForm, ProblemTagForm, OtherItemDispatchForm)
from .filters import ProdReportFilter, StockFilter, DispatchFilter, InwardFilter



@login_required(login_url='/login/')
@accessview
def inwardlist(request):
    inward_list = Inward.objects.all()
    myFilter = InwardFilter(request.GET, inward_list)
    inward_list = myFilter.qs
    totalcount = inward_list.count()
    page = request.GET.get('page', 1)
    paginator = Paginator(inward_list, 100)
    try:
        inward = paginator.page(page)
    except PageNotAnInteger:
        inward = paginator.page(1)
    except EmptyPage:
        inward = paginator.page(paginator.num_pages)
    return render(request, 'inward/list.html', {'inward': inward, 'myFilter': myFilter, 'count': totalcount})


@login_required(login_url='/login/')
@accessview
def inwarddetail(request, id):
    inward = get_object_or_404(Inward, id=id)
    context = {}
    context['inward'] = inward
    context['inward_list'] = inward.stock.all().order_by('materialname', 'item_mat_type',
                                                         'item_grade', 'size', 'micron')
    return render(request, 'inward/inwarddetail.html', context)

@login_required(login_url='/login/')
@accessview
def inwardsummry(request, id):
    inward = get_object_or_404(Inward, id=id)
    context = {}
    context['inward'] = inward
    context['inward_list'] = inward.stock.all().order_by('materialname', 'item_mat_type',
                                                         'item_grade', 'size', 'micron')
    return render(request, 'inward/inwardsummry.html', context)


@login_required(login_url='/login/')
@accessview
def inwardadd(request):
    context = {}
    if request.method == 'POST':
        main_form = InwardForm(request.POST)
        context['main_form'] = main_form
        if main_form.is_valid():
            inward = main_form.save(commit=False)
            inward.createdby = request.user
            inward.save()
            return redirect('production:inwardedit', id=inward.id)
        else:

            return render(request, 'inward/inwardadd.html', context)
    else:
        main_form = InwardForm()
        context['main_form'] = main_form
        return render(request, 'inward/inwardadd.html', context)


@login_required(login_url='/login/')
@accessview
def inwardedit(request, id):
    instance = get_object_or_404(Inward, id=id)
    context = {}
    user = request.user
    formset1 = generic_inlineformset_factory(Stockdetail, form=InwardMaterialForm, extra=10)

    if request.method == 'POST':
        main_form = InwardForm(request.POST or None, instance=instance)
        inwardformset = formset1(request.POST or None, prefix='inwardformset', instance=instance)
        context['main_form'] = main_form
        context['inward_form'] = inwardformset
        if main_form.is_valid() and inwardformset.is_valid():
            main_form.save()
            inwardformset.save()
            main_form = InwardForm(instance=instance)
            inwardformset = formset1(prefix='inwardformset', instance=instance)
            context['main_form'] = main_form
            context['inward_form'] = inwardformset
            messages.success(request, 'save succesfully')
            return render(request, 'inward/inwarddetailedit.html', context)
        else:

            messages.warning(request, 'something went wrong')
            return render(request, 'inward/inwarddetailedit.html', context)
    else:
        main_form = InwardForm(instance=instance)
        inwardformset = formset1(prefix='inwardformset', instance=instance)
        context['main_form'] = main_form
        context['inward_form'] = inwardformset
        return render(request, 'inward/inwarddetailedit.html', context)


@login_required(login_url='/login/')
@accessview
def addprodreport(request):
    id = request.GET.get('q', None)
    jobprocess = get_object_or_404(JobProcess, id=id)
    context = {}
    if request.method == 'POST':
        main_form = NewProdReportForm(request.POST)
        context['main_form'] = main_form
        if main_form.is_valid():
            production = main_form.save(commit=False)
            production.createdby = request.user
            production.prodprocess=jobprocess
            production.save()
            messages.success(request, 'report created succesfully')
            return redirect('production:prodreportdetail', id=production.id)
        else:

            return render(request, 'prodreport/add.html', context)
    else:
        main_form = NewProdReportForm()
        context['instance'] = jobprocess
        context['main_form'] = main_form
        return render(request, 'prodreport/add.html', context)


@login_required(login_url='/login/')
@accessview
def prodreportedit(request, id=None):
    instance = get_object_or_404(ProdReport, id=id)
    parent = get_object_or_404(JobProcess, id=instance.prodprocess.id)
    context = {}
    user = request.user
    formset1 = generic_inlineformset_factory(Stockdetail, form=ProdOutputForm, extra=5)
    formset2 = inlineformset_factory(ProdReport, ProdInput, form=ProdInputForm)
    parentform = modelform_factory(JobProcess, fields=('status',))
    if request.method == 'POST':
        main_form = ProdReportForm(request.POST or None, instance=instance)
        statusform = parentform(request.POST, instance=parent, prefix='statusform')
        prodformset = formset1(request.POST or None, prefix='prodformset', instance=instance)
        inputformset = formset2(request.POST or None, prefix='inputformset', instance=instance,
                                form_kwargs={'prodreport': instance, 'createdby': user})
        context['main_form'] = main_form
        context['statusform'] = statusform
        context['prod_form'] = prodformset
        context['input_form'] = inputformset
        context['instance'] = instance
        if main_form.is_valid() and prodformset.is_valid() and inputformset.is_valid() and statusform.is_valid():
            main_form.save()
            statusform.save()
            prodformset.save()
            inputformset.save()
            messages.success(request, 'report saved ')
            return redirect('production:prodreportedit', id=id)
        else:

            messages.success(request, 'something gone wrong')
            return render(request, 'prodreport/reportedit.html', context)
    else:
        main_form = ProdReportForm(instance=instance)
        statusform = parentform(instance=parent, prefix='statusform')
        prodformset = formset1(prefix='prodformset', instance=instance)
        inputformset = formset2(prefix='inputformset', instance=instance,
                                form_kwargs={'prodreport': instance, 'createdby': user})
        context['main_form'] = main_form
        context['statusform'] = statusform
        context['prod_form'] = prodformset
        context['input_form'] = inputformset
        context['instance'] = instance
        return render(request, 'prodreport/reportedit.html', context)


@login_required(login_url='/login/')
@accessview
def prodreportaddinput(request, id=None):
    instance = get_object_or_404(ProdReport, id=id)
    if request.method == 'POST':
        inputform = ProdInputBlankForm(request.POST or None, prodreport=instance)

        if inputform.is_valid():
            a = inputform.save(commit=False)
            a.prodreport = instance
            a.save()

            messages.success(request, 'New roll added successfully')
            return redirect('production:prodreportdetail', id=id)
        else:

            messages.success(request, 'Failed to create new Roll')
            messages.success(request, inputform.errors)
            return redirect('production:prodreportdetail', id=id)
    else:
        inputform = ProdInputBlankForm(prodreport=instance)
        return render(request, "prodinputhtmx.html", {"inputform": inputform})


@login_required(login_url='/login/')
@accessview
def prodreporteditinput(request, id=None):
    next = request.GET.get("next")

    instance = get_object_or_404(ProdInput, id=id)
    prodreport = instance.prodreport_id
    context = {}
    context['prodreport'] = prodreport
    if request.method == 'POST':
        inputform = ProdInputEditForm(request.POST or None, instance=instance)
        context['inputform'] = inputform
        if inputform.is_valid():
            inputform.save()
            messages.success(request, 'Input detail Updated Succesflluy')
            if next:
                return redirect(next)

            return redirect('production:prodreportdetail', id=prodreport)
        else:
            messages.success(request, 'Failed to Edit Input')
            messages.success(request, inputform.errors)
            return redirect('production:prodreportdetail', id=prodreport)
    else:
        inputform = ProdInputEditForm(instance=instance)
        context['inputform'] = inputform
        return render(request, 'prodreport/editinput.html', context)


@login_required(login_url='/login/')
@accessview
def prodreporteditoutput(request, id=None):
    instance = get_object_or_404(Stockdetail, id=id)
    TagsInlineFormSet = inlineformset_factory(Stockdetail, ProblemTag, form=ProblemTagForm,can_order = True)
    problemformset = TagsInlineFormSet(request.POST or None,instance=instance)
    prodreport = instance.object_id
    context = {}
    context['prodreport'] = prodreport
    context['problemformset']= problemformset
    outputform = ProdOutputAddForm(request.POST or None, instance=instance)
    context['outputform'] = outputform

    if request.method == 'POST':
        if outputform.is_valid() and problemformset.is_valid():
            outputform.save()
            problemformset.save()
            messages.success(request, 'Output detail Updated Succesfully')
            return redirect('production:prodreportdetail', id=prodreport)
        else:

            messages.success(request, 'Failed to Edit Output')
            return redirect('production:prodreportdetail', id=prodreport)
    else:
        return render(request, 'prodreport/editoutput.html', context)


@login_required(login_url='/login/')
@accessview
def prodreportaddoutput(request, id=None):
    instance = get_object_or_404(ProdReport, id=id)
    ct = ContentType.objects.get_for_model(model=instance)
    if request.method == 'POST':
        outputform = ProdOutputAddForm(request.POST or None, initial={'content_type': ct, 'object_id': id})
        if outputform.is_valid():
            a = outputform.save(commit=False)
            a.save()
            messages.success(request, 'New roll added successfully')
            return redirect('production:prodreportdetail', id=id)
        else:
            messages.success(request, 'Failed to create output Roll')
            messages.success(request, outputform.errors)
            return redirect('production:prodreportdetail', id=id)


@login_required(login_url='/login/')
@accessview
def prodreportaddperson(request, id=None):
    instance = get_object_or_404(ProdReport, id=id)
    personform = modelform_factory(ProdPerson, fields=('person',), )

    if request.method == 'POST':
        form = personform(request.POST or None)

        if form.is_valid():
            a = form.save(commit=False)
            a.prodreport = instance
            a.save()
            return redirect('production:prodreportdetail', id=id)
        else:
            messages.success(request, form.errors)
            return redirect('production:prodreportdetail', id=id)
    else:
        return redirect('production:prodreportdetail', id=id)


@login_required(login_url='/login/')
@accessview
def prodreportaddproblem(request, id=None):
    instance = get_object_or_404(ProdReport, id=id)
    problemform = modelform_factory(ProdProblem, fields=('problem', 'timewaste', 'action',), )

    if request.method == 'POST':
        form = problemform(request.POST or None)

        if form.is_valid():
            a = form.save(commit=False)
            a.prodreport = instance
            a.save()
            return redirect('production:prodreportdetail', id=id)
        else:
            messages.success(request, form.errors)
            return redirect('production:prodreportdetail', id=id)
    else:
        return redirect('production:prodreportdetail', id=id)


@login_required(login_url='/login/')
@accessview
def prodreportdetail(request, id=None):
    instance = get_object_or_404(ProdReport, id=id)
    ct = ContentType.objects.get_for_model(model=instance)
    parent = get_object_or_404(JobProcess, id=instance.prodprocess.id)
    inputdetail = instance.prodinput.all()
    outputdetail = instance.output.all().order_by("id")
    persons = instance.prodperson.all()
    problems = instance.prodproblem.all()
    jobqc=instance.jobqc.all()
    context = {}
    context['instance'] = instance
    context['parent'] = parent
    context['inputs'] = inputdetail
    context['outputs'] = outputdetail
    context['persons'] = persons
    context['problems'] = problems
    context['jobqc']=jobqc
    parentform = modelform_factory(JobProcess, fields=('status',))
    if request.method == 'POST':
        main_form = ProdReportForm(request.POST or None, instance=instance)
        statusform = parentform(request.POST, instance=parent, prefix='statusform')
        context['main_form'] = main_form
        context['statusform'] = statusform
        if main_form.is_valid() and statusform.is_valid():
            main_form.save()
            statusform.save()
            messages.success(request, 'report saved ')
            return redirect('production:prodreportdetail', id=id)
        else:
            messages.success(request, 'something gone wrong')
            return render(request, 'report/detail.html', context)
    else:
        main_form = ProdReportForm(instance=instance)
        statusform = parentform(instance=parent, prefix='statusform')
        outputform = ProdOutputAddForm(initial={'content_type': ct, 'object_id': id})
        inputform = ProdInputBlankForm(prodreport=instance)
        personform = AddPersonForm()
        problemform = modelform_factory(ProdProblem, fields=('problem', 'timewaste', 'action',), )
        context['main_form'] = main_form
        context['statusform'] = statusform
        context['inputform'] = inputform
        context['outputform'] = outputform
        context['personform'] = personform
        context['problemform'] = problemform
        context['jobqcform']=AddJobQcForm(instance=instance)
        return render(request, 'report/detail.html', context)


@login_required(login_url='/login/')
@accessview
def prodreportlist(request, status=None):
    if status == "All" or status == None:
        prod_list = ProdReport.objects.select_related().all()
    else:
        prod_list = ProdReport.objects.select_related().filter(prodprocess__process__process=status)

    myFilter = ProdReportFilter(request.GET, prod_list)
    prod_list = myFilter.qs
    totalcount = prod_list.count()

    page = request.GET.get('page', 1)
    paginator = Paginator(prod_list, 100)
    try:
        reports = paginator.page(page)
    except PageNotAnInteger:
        reports = paginator.page(1)
    except EmptyPage:
        reports = paginator.page(paginator.num_pages)

    return render(request, 'prodreport/reportlist.html',
                  {'reports': reports, 'total': totalcount, 'myFilter': myFilter})


@login_required(login_url='/login/')
@accessview
def stocklist(request):
    stock_list = Stockdetail.objects.select_related('materialname', 'item_mat_type', 'item_grade',
                                                    'content_type').annotate(
        allote=(Sum('jobmaterialstatus__qty', distinct=True)) or 0)

    if request.GET.get("ordering"):
        ordering = request.GET.get("ordering").split(".")
        if ordering:
            stock_list = stock_list.order_by(*ordering)
    else:
        stock_list = stock_list.order_by()
    myFilter = StockFilter(request.GET, stock_list)
    stock_list = myFilter.qs.select_related('materialname', 'item_mat_type', 'item_grade',
                                            'content_type').annotate(
        allote=(Sum('jobmaterialstatus__qty', distinct=True)) or 0)
    totalcount = stock_list.count()
    totalbalance = stock_list.aggregate(Sum('balance'))

    page = request.GET.get('page', 1)
    paginator = Paginator(stock_list, 100)

    try:
        stocks = paginator.page(page)
    except PageNotAnInteger:
        stocks = paginator.page(1)
    except EmptyPage:
        stocks = paginator.page(paginator.num_pages)

    return render(request, 'stock/stocklist.html', {'stocks': stocks, 'total': totalcount, 'myFilter': myFilter,
                                                    'totalbalance': totalbalance})


@login_required(login_url='/login/')
@accessview
def jobmaterialstatusedit(request, id=None):
    jobmaterial = get_object_or_404(JobMaterial, id=id)
    mate = jobmaterial.materialname
    sizes = jobmaterial.size - 15
    mate_type = jobmaterial.item_mat_type
    can_delete = request.user.username=="khadimhusen" or request.user.username=="admin"
    context = {}
    context['jobmaterial'] = jobmaterial
    formset1 = inlineformset_factory(JobMaterial, JobMaterialStatus, form=JobMaterialStatusForm,can_delete=can_delete)
    mainform = Jobmaterialtoroder(request.POST or None, instance=jobmaterial)

    if request.method == "POST":
        matform = formset1(request.POST or None, instance=jobmaterial,
                           form_kwargs={'mate': mate, 'sizes': sizes, 'mate_type': mate_type})
        context['matform'] = matform
        context['mainform'] = mainform

        if matform.is_valid() and mainform.is_valid():
            mainform.save()
            matform.save()
            return redirect('order:jobdetail', id=jobmaterial.job.id)
        else:
            return render(request, 'jobmaterialstatus/edit.html', context)

    else:

        matform = formset1(instance=jobmaterial, form_kwargs={'mate': mate, 'sizes': sizes, 'mate_type': mate_type})
        context['matform'] = matform
        context['mainform'] = mainform
        return render(request, 'jobmaterialstatus/edit.html', context)

    # -------------------------------------------------------------------------------------#


@login_required(login_url='/login/')
@accessview
def dispatchlist(request):
    dispatch_list = DispatchRegister.objects.all()

    myFilter = DispatchFilter(request.GET, dispatch_list)
    dispatch_list = myFilter.qs
    totalcount = dispatch_list.count()

    page = request.GET.get('page', 1)
    paginator = Paginator(dispatch_list, 100)

    try:
        dispatch = paginator.page(page)
    except PageNotAnInteger:
        dispatch = paginator.page(1)
    except EmptyPage:
        dispatch = paginator.page(paginator.num_pages)

    return render(request, 'dispatch/list.html', {'dispatch': dispatch, 'myFilter': myFilter, 'totalcount': totalcount})


@login_required(login_url='/login/')
@accessview
def dispatchadd(request):
    context = {}
    if request.method == 'POST':
        dispatch_form = DispatchNewForm(request.POST)
        context['dispatch_form'] = dispatch_form
        if dispatch_form.is_valid():
            dispatch = dispatch_form.save(commit=False)
            dispatch.createdby = request.user
            dispatch.save()
            messages.success(request, "New Dispatch Added.")
            return HttpResponseRedirect(reverse('production:dispatchdetailedit', kwargs={'id': dispatch.id}))
        else:

            return render(request, 'dispatch/add.html', context)
    else:
        dispatch_form = DispatchNewForm()
        context['dispatch_form'] = dispatch_form
        return render(request, 'dispatch/add.html', context)


@login_required(login_url='/login/')
@accessview
def dispatchlock(request, id=None):
    DispatchRegister.objects.filter(id=id).update(lock=True)

    return HttpResponse("return done")


@login_required(login_url='/login/')
@accessview
def dispatchunlock(request, id=None):
    DispatchRegister.objects.filter(id=id).update(lock=False)

    return HttpResponse("return done")


@login_required(login_url='/login/')
@accessview
def dispatchdetailedit(request, id=None):
    disp = get_object_or_404(DispatchRegister, id=id)
    formset=inlineformset_factory(DispatchRegister,OtherDispatchItem,OtherItemDispatchForm,can_delete=True,max_num=12)
    otheritemform=formset(request.POST or None,instance=disp)
    displock = disp.lock
    context = {}
    context['disp'] = disp

    pendingmate = []
    pendingmaterial = Stockdetail.objects.filter(
        prodreports__prodprocess__job__joborder__customer__id=disp.customer.id, dispached__isnull=True,
        qc_status="Finished", prodreports__prodprocess__job__dispatch_approval=True,
        prodreports__checked=False) | Stockdetail.objects.filter(
        prodreports__prodprocess__job__joborder__customer__id=disp.customer.id, dispached__isnull=True,
        qc_status="Finished", prodreports__prodprocess__job__dispatch_approval=True,
        prodreports__approved=False)
    for obj in pendingmaterial:
        pendingmate.append(
            f"{obj.prodreports.all().first().prodprocess.job.itemname}= Gross Wt. {obj.gross_wt}")
    context["pendingmaterial"] = pendingmate

    if displock:
        dispatchedlist = [
            f"{ item.prodreports.first().prodprocess.job.rate}/{item.prodreports.first().prodprocess.job.unit}-{item.prodreports.first().prodprocess.job.itemname}= Gross Wt. {item.gross_wt}"
            for item in disp.dispatch_material.all()]
        context['dispatchedlist'] = dispatchedlist

    if request.method == 'POST' :
        dispatch_form = DispatchForm(request.POST, request.FILES or None,instance=disp)
        context['dispatch_form'] = dispatch_form
        context['otheritemform'] = otheritemform
        if dispatch_form.is_valid() and otheritemform.is_valid():
            dispatch = dispatch_form.save(commit=False)
            dispatch.editedby = request.user
            dispatch.save()
            otheritemform.save()

            if not displock:
                otheritemform.save()
                dispatch_form.save_m2m()
            return HttpResponseRedirect(reverse('production:dispatchdetail', kwargs={'id': dispatch.id}))
        else:

            return render(request, 'dispatch/dispatchdetailedit.html', context)
    else:
        dispatch_form = DispatchForm( instance=disp)
        context['otheritemform'] = otheritemform
        context['dispatch_form'] = dispatch_form
        return render(request, 'dispatch/dispatchdetailedit.html', context)

@login_required(login_url='/login/')
@accessview
def materialdetail(request, id=None):
    mat = get_object_or_404(Stockdetail, id=id)
    context = {}
    context['material'] = mat
    formset1 = inlineformset_factory(Stockdetail, JobMaterialStatus, JobAllotementForm, extra=1)
    if request.method == "POST":
        materialform = formset1(request.POST or None, instance=mat)
        context['matforms'] = materialform
        if materialform.is_valid():
            materialform.save()
            return redirect('production:stocklist')
        else:
            messages.warning(request, materialform.errors)
            return render(request, 'stock/materialdetailedit.html', context)

    else:
        materialform = formset1(instance=mat)
        context['matforms'] = materialform
        return render(request, 'stock/materialdetailedit.html', context)


@login_required(login_url='/login/')
@accessview
def dispatchpending(request):
    obj = {}
    material_list = Stockdetail.objects.filter(dispached__isnull=True,
                                               qc_status="Finished",
                                               recieved__gt=0.001,
                                               prodreports__prodprocess__job__dispatch_approval=True
                                               ).prefetch_related(
        "content_object__prodprocess__job__itemmaster").order_by('prodreports__prodprocess__job__joborder__customer')

    for material in material_list:
        cust = material.content_object.prodprocess.job.joborder.customer.name
        jobname = material.content_object.prodprocess.job
        orderqty = material.content_object.prodprocess.job.kgqty

        if not cust in obj:
            jobs = {}
            jobs[jobname] = {'qty': material.recieved,'nos':material.nos or 0, 'po':jobname.joborder.po,
                             'orderqty': orderqty, 'remark': jobname.dispatch_remark}
            obj[cust] = jobs

        else:
            if jobname in obj[cust]:
                obj[cust][jobname]['qty'] += material.recieved
                obj[cust][jobname]['nos'] += (material.nos or 0)
            else:
                obj[cust][jobname] = {'qty': material.recieved,'nos':material.nos or 0,'po':jobname.joborder.po,
                                                'orderqty': orderqty, 'remark': jobname.dispatch_remark}

    return render(request, 'finishedmaterial/dispatchpending.html', {"obj": sorted(obj.items())})


@login_required(login_url='/login/')
@accessview
def dispatchapproval(request, id=None):
    instance = get_object_or_404(Job, id=id)
    if request.method == 'POST':
        dispform = DispatchApprovalForm(request.POST, instance=instance)

        if dispform.is_valid():
            a = dispform.save(commit=False)
            a.dispatch_approval_date = datetime.datetime.now()
            a.save()
            messages.success(request, 'Approval Done ')
        else:
            messages.warning(request, 'Approval Not Done')

    return redirect("production:dispatchapprovalpending")


@login_required(login_url='/login/')
@accessview
def dispatchapprovalpending(request):
    obj = {}
    customerlist = []
    material_list = Stockdetail.objects.filter(dispached__isnull=True,
                                               qc_status="Finished",
                                               recieved__gt=0.001,
                                               prodreports__prodprocess__job__dispatch_approval=False,
                                               prodreports__prodprocess__job__jobstatus__in=["Completed",
                                                                                             "Partially Ready"]
                                               ).prefetch_related(
        "content_object__prodprocess__job__itemmaster").order_by('prodreports__prodprocess__job__joborder__customer')

    for material in material_list:
        cust = material.content_object.prodprocess.job.joborder.customer.name
        jobname = material.content_object.prodprocess.job
        orderqty = material.content_object.prodprocess.job.kgqty

        if not cust in obj:
            jobs = {}
            jobs[jobname] = {'qty': material.recieved, 'orderqty': orderqty,
                             "disp_app_form": DispatchApprovalForm(instance=jobname,
                                                                   initial={'dispatch_approval': True})}
            obj[cust] = jobs
            customerlist.append(cust)

        else:
            if jobname in obj[cust]:
                obj[cust][jobname]['qty'] += material.recieved
            else:
                obj[cust][jobname] = {'qty': material.recieved, 'orderqty': orderqty,
                                      "disp_app_form": DispatchApprovalForm(instance=jobname,
                                                                            initial={'dispatch_approval': True})}
    return render(request, 'finishedmaterial/dispatchapprovalpending.html', {"obj": sorted(obj.items())})


@login_required(login_url='/login/')
@accessview
def dispatchapprovalpending1(request):
    obj = []
    customerlist = []
    material_list = Stockdetail.objects.filter(dispached__isnull=True,
                                               qc_status="Finished",
                                               recieved__gt=0.001,
                                               prodreports__prodprocess__job__dispatch_approval=False
                                               ).prefetch_related(
        "content_object__prodprocess__job__itemmaster").order_by('prodreports__prodprocess__job__joborder__customer')

    for material in material_list:
        cust = material.content_object.prodprocess.job.joborder.customer.name
        jobname = material.content_object.prodprocess.job
        orderqty = material.content_object.prodprocess.job.kgqty

        for item in obj:
            if item.key == cust:
                jobs = {}
                jobs[jobname] = {'qty': material.recieved, 'orderqty': orderqty,
                                 "dips_app_form": DispatchApprovalForm(instance=jobname,
                                                                       initial={'dispatch_approval': True})}
                obj.append({cust: {jobs}})
                customerlist.append(cust)
                break

            else:
                if jobname in obj[cust]:
                    obj[cust][jobname]['qty'] += material.recieved
                else:
                    obj[cust][jobname] = {'qty': material.recieved, 'orderqty': orderqty,
                                          "dips_app_form": DispatchApprovalForm(instance=jobname,
                                                                                initial={'dispatch_approval': True})}

    return render(request, 'finishedmaterial/dispatchapprovalpending.html',
                  {'material_list': material_list, "obj": obj, 'customerlist': customerlist})


@login_required(login_url='/login/')
@accessview
def dispatchdetail(request, id=None):
    context = {}
    dispatchregister = get_object_or_404(DispatchRegister, id=id)
    context["dispatch_list"] = dispatchregister.dispatch_material.all().order_by(
        "prodreports__prodprocess__job__itemname")
    context['dispatch'] = dispatchregister
    return render(request, 'dispatch/dispatchdetail.html', context)


@login_required(login_url='/login/')
@accessview
def singlemaaterialedit(request, id=None):
    instance = get_object_or_404(Stockdetail, id=id)
    context = {'instance': instance}
    if request.method == 'POST':
        form = StockMaterailEditForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, 'materail status updated ')
        return redirect('production:stocklist')
    else:
        form = StockMaterailEditForm(instance=instance)
        context['form'] = form
        return render(request, 'stock/singlematerailedit.html', context)


@login_required(login_url='/login/')
@accessview
def changevalue(request):
    tomate = get_object_or_404(Material, name="WASTE")

    items = Stockdetail.objects.filter(qc_status="Ok", balance__lte=0)

    for item in list(items):
        item.qc_status = "Nil"

    items.bulk_update(list(items), ["qc_status"])
    return redirect('production:stocklist', status="All")


@login_required(login_url='/login/')
@accessview
def stockdetail(request, id=None):
    stock = get_object_or_404(Stockdetail, id=id)
    return render(request, 'stock/test.html', {"stock": stock})


@login_required(login_url='/login/')
@accessview
def addinputhtmx(request, id):
    context = {}
    instance = get_object_or_404(ProdReport, id=id)
    inputdetail = instance.prodinput.all()
    context['inputs'] = inputdetail
    context['instance'] = instance

    if request.method == 'POST':
        inputform = ProdInputBlankForm(request.POST or None, prodreport=instance)
        if inputform.is_valid():
            a = inputform.save(commit=False)
            a.prodreport = instance
            a.save()
            messages.success(request, 'Input Entry Done Successfully')
            inputform = ProdInputBlankForm(prodreport=instance)
            context['inputform'] = inputform
            return render(request, 'htmx/inputhtmx.html', context)
        else:
            messages.success(request, 'Input Entry FAILED, Please Refresh webpage and try again. ')
            messages.success(request, inputform.errors)
            inputform = ProdInputBlankForm(prodreport=instance)
            context['inputform'] = inputform
            return render(request, 'htmx/inputhtmx.html', context)
    else:
        inputform = ProdInputBlankForm(prodreport=instance)
        context['inputform'] = inputform
        return render(request, 'htmx/inputhtmx.html', context)


@login_required(login_url='/login/')
@accessview
def addoutputhtmx(request, id=None):
    context = {}
    instance = get_object_or_404(ProdReport, id=id)
    ct = ContentType.objects.get_for_model(model=instance)
    outputdetail = instance.output.all().order_by("id")
    context['outputs'] = outputdetail
    context['instance'] = instance
    if request.method == 'POST':
        outputform = ProdOutputAddForm(request.POST or None, initial={'content_type': ct, 'object_id': id})
        if outputform.is_valid():
            a = outputform.save(commit=False)
            a.save()
            messages.success(request, 'Output Entry Done Successfully!')
            outputform = ProdOutputAddForm(initial={'content_type': ct, 'object_id': id})
            context['outputform'] = outputform
            return render(request, 'htmx/outputhtmx.html', context)
        else:
            messages.success(request, 'Failed to create output Roll')
            messages.success(request, outputform.errors)
            outputform = ProdOutputAddForm(initial={'content_type': ct, 'object_id': id})
            context['outputform'] = outputform
            return render(request, 'htmx/outputhtmx.html', context)
    else:
        outputform = ProdOutputAddForm(initial={'content_type': ct, 'object_id': id})
        context['outputform'] = outputform
        return render(request, 'htmx/outputhtmx.html', context)


@login_required(login_url='/login/')
@accessview
def addpersonhtmx(request, id=None):
    context = {}
    instance = get_object_or_404(ProdReport, id=id)
    persons = instance.prodperson.all()
    context['persons'] = persons
    context['instance'] = instance
    if request.method == 'POST':
        form = AddPersonForm(request.POST or None)
        if form.is_valid():
            a = form.save(commit=False)
            a.prodreport = instance
            a.save()
            messages.success(request, 'Entry Done Successfully!')
            form = AddPersonForm()
            context['personform'] = form
            return render(request, 'htmx/personhtmx.html', context)
        else:
            messages.success(request, 'Something Went Wrong!')
            messages.success(request, form.errors)
            form = AddPersonForm()
            context['personform'] = form
            return render(request, 'htmx/personhtmx.html', context)
    else:
        form = AddPersonForm()
        context['personform'] = form
        return render(request, 'htmx/personhtmx.html', context)


@login_required(login_url='/login/')
@accessview
def addproblemhtmx(request, id=None):
    context = {}
    instance = get_object_or_404(ProdReport, id=id)
    problems = instance.prodproblem.all()
    context['problems'] = problems
    context['instance'] = instance
    if request.method == 'POST':
        form = AddProblemForm(request.POST or None)
        if form.is_valid():
            a = form.save(commit=False)
            a.prodreport = instance
            a.save()
            messages.success(request, 'Entry Done Successfully!')
            form = AddProblemForm()
            context['problemform'] = form
            return render(request, 'htmx/problemhtmx.html', context)
        else:
            messages.success(request, 'Something Went Wrong!')
            messages.success(request, form.errors)
            form = AddProblemForm()
            context['problemform'] = form
            return render(request, 'htmx/problemhtmx.html', context)
    else:
        form = AddProblemForm()
        context['problemform'] = form
        return render(request, 'htmx/problemhtmx.html', context)

@login_required(login_url='/login/')
@accessview
def addjobqchtmx(request, id=None):
    context = {}
    instance = get_object_or_404(ProdReport, id=id)
    jobqc = instance.jobqc.all()
    context['jobqc'] = jobqc
    context['instance'] = instance
    if request.method == 'POST':
        form = AddJobQcForm(request.POST or None)
        if form.is_valid():
            a = form.save(commit=False)
            a.prodreport = instance
            a.createdby = request.user
            a.save()
            messages.success(request, 'qc Entry Done Successfully!')
            form = AddJobQcForm(instance=instance)
            context['jobqcform'] = form
            return render(request, 'htmx/jobqchtmx.html', context)
        else:
            messages.success(request, 'Something Went Wrong!')
            messages.success(request, form.errors)
            form = AddJobQcForm(instance=instance)
            context['jobqcform'] = form
            return render(request, 'htmx/jobqchtmx.html', context)
    else:
        form = AddJobQcForm(instance=instance)
        context['jobqcform'] = form
        return render(request, 'htmx/jobqchtmx.html', context)
