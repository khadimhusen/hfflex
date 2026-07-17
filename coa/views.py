from datetime import datetime
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from order.models import Job

from django.contrib.admin.views.decorators import staff_member_required
from myproject.access import accessview
from .forms import CoaForm, TestParameterForm, CoaAdminForm
from django.forms import inlineformset_factory

from django.shortcuts import render, get_object_or_404, redirect

from django.contrib.auth.decorators import login_required
from .models import Coa, TestParameter
from order.models import JobCoa


@login_required(login_url='/login/')
@accessview
def add_coa(request, jobid=None, dcid=None):
    try:
        coa = Coa.objects.get(jobname_id=jobid, delivery_challan_id=dcid)
        return HttpResponseRedirect(reverse('coa:coadetail', kwargs={'pk': coa.id}))
    except:

        job = get_object_or_404(Job, id=jobid)

        context = {}

        if request.method == 'POST':
            coaform = CoaForm(request.POST)
            context['newcoaform'] = coaform
            if coaform.is_valid():
                newcoa = coaform.save(commit=False)
                newcoa.createdby = request.user
                newcoa.jobname = job
                newcoa.save()
                return HttpResponseRedirect(reverse('coa:coaedit', kwargs={'id': newcoa.id}))
            else:
                return render(request, 'coa/newcoa.html', context)
        else:
            if dcid:
                dc = get_object_or_404(Job, id=dcid)
                coaform = CoaForm(initial={'delivery_challan': dc})
            else:
                coaform = CoaForm()
            context['newcoaform'] = coaform
            return render(request, 'coa/newcoa.html', context)


@login_required(login_url='/login/')
@accessview
def coa_edit(request, id):
    coa = get_object_or_404(Coa.objects.select_related('jobname__itemmaster'), id=id)
    TestFormSet = inlineformset_factory(
        Coa, TestParameter, form=TestParameterForm,
        extra=12, can_delete=True,max_num=20
    )
    if coa.is_approved:
        messages.error(
            request,
            f"COA {coa.coa_number} is already approved and cannot be edited."
        )
        return redirect('coa:coadetail', pk=coa.pk)

    if request.method == 'POST':
        coaform = CoaForm(request.POST, instance=coa)
        testform = TestFormSet(request.POST, instance=coa, form_kwargs={'coa': coa})

        if coaform.is_valid() and testform.is_valid():
            coa_instance = coaform.save(commit=False)
            coa_instance.editedby = request.user
            coa_instance.save()
            testform.save()
            messages.success(request, "Data saved successfully")
            return HttpResponseRedirect(reverse('coa:coaedit', kwargs={'id': coa_instance.id}))
        else:
            messages.error(request, "Something went wrong")
    else:
        coaform = CoaForm(instance=coa)
        testform = TestFormSet(instance=coa, form_kwargs={'coa': coa})

    context = {'coa': coa, 'coaform': coaform, 'testform': testform}
    return render(request, 'coa/coaedit.html', context)


@login_required(login_url='/login/')
@accessview
def coa_detail(request, pk):
    coa = get_object_or_404(
        Coa.objects.select_related(
            'jobname',
            'jobname__itemmaster',
            'delivery_challan',
            'createdby',
            'approvedby',
            'editedby',
        ),
        pk=pk
    )

    # Specification values from the job's COA spec sheet
    job_coa_specs = (
        JobCoa.objects
        .filter(job=coa.jobname)
        .select_related('standard_parameter')
    )

    # Build a lookup: {standard_parameter_id: spec_value}
    spec_lookup = {
        jc.standard_parameter_id: jc.value
        for jc in job_coa_specs
    }

    # Actual tested results recorded on this COA
    test_parameters = (
        TestParameter.objects
        .filter(coa=coa)
        .select_related('standard_parameter')
        .order_by('standard_parameter__parameter')
    )

    # Attach the spec value to each test parameter row
    rows = []
    for tp in test_parameters:
        rows.append({
            'parameter': tp.standard_parameter.parameter,
            'unit': tp.standard_parameter.unit_of_measure,
            'specification': spec_lookup.get(tp.standard_parameter_id, '—'),
            'result': tp.result,
        })

    context = {
        'coa': coa,
        'rows': rows,
    }
    return render(request, 'coa/coadetail.html', context)


@login_required(login_url='/login/')
@accessview
def add_test_parameter(request, coa_id):
    coa = get_object_or_404(
        Coa.objects.select_related('jobname__itemmaster'),
        pk=coa_id,
    )

    if request.method == 'POST':
        form = TestParameterForm(request.POST, coa=coa)
        if form.is_valid():
            tp = form.save(commit=False)
            tp.coa = coa
            tp.save()
            return redirect('coa:coa_detail', pk=coa.pk)
    else:
        form = TestParameterForm(coa=coa, initial={'coa': coa})

    return render(request, 'coa/test_parameter_form.html', {
        'form': form,
        'coa': coa,
    })


@login_required(login_url='/login/')
@accessview
def coa_approve(request, pk):
    coadetail = get_object_or_404(Coa, pk=pk)

    # Server-side verification
    if request.method != 'POST':
        messages.warning(request, 'Invalid request method.')
        return HttpResponseRedirect(reverse('coa:coadetail', kwargs={'pk': pk}))
    else:
        coadetail.approvedby = request.user
        coadetail.approve_date = datetime.now()
        coadetail.save()
        messages.success(request, 'Coa is Approved')
        return HttpResponseRedirect(reverse('coa:coadetail', kwargs={'pk': pk}))




@login_required(login_url='/login/')
@staff_member_required
def coa_reopen(request, pk):
    coa = get_object_or_404(Coa, pk=pk)

    if request.method == 'POST':
        coa.approvedby = None
        coa.approve_date = None
        coa.save(update_fields=['approvedby', 'approve_date'])
        messages.warning(
            request,
            f"COA {coa.coa_number} has been reopened for editing."
        )
        return redirect('coa:coadetail', pk=coa.pk)

    return render(request, 'coa/coa_reopen_confirm.html', {'coa': coa})

@login_required(login_url='/login/')
def coa_admin_edit(request, pk):
    """Administrative fields — always editable, even after approval."""
    coa = get_object_or_404(Coa, pk=pk)

    if request.method == 'POST':
        form = CoaAdminForm(request.POST, instance=coa)
        if form.is_valid():
            coa = form.save(commit=False)
            coa.editedby = request.user
            coa.save()
            messages.success(
                request,
                f"Administrative details updated for COA {coa.coa_number}."
            )
            return redirect('coa:coadetail', pk=coa.pk)
    else:
        form = CoaAdminForm(instance=coa)

    return render(request, 'coa/coa_admin_edit.html', {
        'coa': coa, 'form': form,
    })