from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from order.models import Job

from myproject.access import accessview
from .forms import CoaForm, TestParameterForm
from django.forms import inlineformset_factory

from django.shortcuts import render, get_object_or_404, redirect

from django.contrib.auth.decorators import login_required
from .models import Coa, TestParameter
from order.models import JobCoa



@login_required(login_url='/login/')
@accessview
def addcoa(request, jobid):
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
        coaform = CoaForm()
        context['newcoaform'] = coaform
        return render(request, 'coa/newcoa.html', context)

@login_required(login_url='/login/')
@accessview
def coaedit(request, id):
    coa = get_object_or_404(Coa, id=id)
    TestFormSet = inlineformset_factory(
        Coa, TestParameter, form=TestParameterForm,
        extra=1, can_delete=True
    )

    if request.method == 'POST':
        coaform = CoaForm(request.POST, instance=coa)
        testform = TestFormSet(request.POST, instance=coa,form_kwargs={'coa':coa})

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
        testform = TestFormSet(instance=coa,form_kwargs={'coa':coa})

    context = {'coa': coa, 'coaform': coaform, 'testform': testform}
    return render(request, 'coa/coaedit.html', context)




@login_required
def coadetail(request, pk):
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



@login_required
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