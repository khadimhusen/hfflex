from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.forms import inlineformset_factory, modelform_factory
from django.shortcuts import render, redirect, get_object_or_404
from manpower.models import Shift, Activity, Machine, ShiftPerson
from myproject.access import accessview
from .filters import ShiftFilter
from .forms import NewShiftForm, ActivityForm, ShiftPersonForm
import datetime

@login_required(login_url='/login/')
@accessview
def shiftlist(request):
    q = request.GET.get('q', None)
    if q != None:
        shift_list = Shift.objects.filter(jobstatus=q)
    else:
        shift_list = Shift.objects.all()

    myFilter = ShiftFilter(request.GET, shift_list)
    shift_list = myFilter.qs
    page = request.GET.get('page', 1)
    paginator = Paginator(shift_list, 100)
    try:
        shifts = paginator.page(page)
    except PageNotAnInteger:
        shifts = paginator.page(1)
    except EmptyPage:
        shifts = paginator.page(paginator.num_pages)

    return render(request, 'shift/shiftlist.html', {"shifts": shifts, 'myFilter': myFilter, })


@login_required(login_url='/login/')
@accessview
def newshift(request):
    context = {}
    user = request.user

    if request.method == 'POST':
        main_form = NewShiftForm(request.POST)
        context['main_form'] = main_form
        print(main_form)

        if main_form.is_valid():
            machineinstance = Machine.objects.filter(machinename=request.user.username).first() or None
            proddate = request.POST['production_date'].split("/")
            if machineinstance:
                proddate = datetime.date(int(proddate[2]), int(proddate[1]), int(proddate[0]))

                obj, created = Shift.objects.get_or_create(
                    shift=request.POST['shift'],
                    machine=machineinstance,
                    production_date=proddate,
                )
                if created:
                    Shift.objects.filter(id=obj.id).update(createdby=request.user)

                return redirect('manpower:shiftdetail', id=obj.id)
            else:
                messages.success(request, "invalid user. User Must be from machine user")
                return render(request, 'shift/newshift.html', context)
        else:
            print(main_form.errors)
            return render(request, 'shift/newshift.html', context)
    else:
        main_form = NewShiftForm()
        context['main_form'] = main_form
        return render(request, 'shift/newshift.html', context)


@login_required(login_url='/login/')
@accessview
def editshift(request, id):
    instance = get_object_or_404(Shift, id=id)
    context = {}
    user = request.user
    formset1 = inlineformset_factory(Shift, model=Activity, form=ActivityForm, extra=1)

    if request.method == 'POST':
        main_form = NewShiftForm(request.POST or None, instance=instance)
        activityformset = formset1(request.POST or None, prefix='activityformset', instance=instance)
        context['main_form'] = main_form
        context['activityformset'] = activityformset
        if main_form.is_valid() and activityformset.is_valid():
            main_form.save()
            activityformset.save()
            main_form = NewShiftForm(instance=instance)
            activityformset = formset1(prefix='activityformset', instance=instance)
            context['main_form'] = main_form
            context['activityformset'] = activityformset
            messages.success(request, 'save succesfully')
            return render(request, 'shift/shiftedit.html', context)
        else:
            print(main_form.errors)
            print(activityformset.errors)
            messages.warning(request, 'something went wrong')
            return render(request, 'shift/shiftedit.html', context)
    else:
        main_form = NewShiftForm(instance=instance)
        activityformset = formset1(prefix='activityformset', instance=instance)
        context['main_form'] = main_form
        context['activityformset'] = activityformset
        return render(request, 'shift/shiftedit.html', context)


@login_required(login_url='/login/')
@accessview
def shiftdetail(request, id=None):
    instance = get_object_or_404(Shift, id=id)
    qperson = request.GET.get('qperson', None)
    qactivity = request.GET.get('qactivity', None)
    activityinstance=None
    personinstance=None
    if qperson:
        personinstance=get_object_or_404(ShiftPerson, id=qperson)
        print( "person instance = ", personinstance)
    if qactivity:
        activityinstance=get_object_or_404(Activity, id=qactivity)
        print( " activity inbstace = ", activityinstance)

    context = {}
    context["instance"] = instance
    personform = ShiftPersonForm
    shiftpersonform=personform(request.POST or None, instance=personinstance, initial={"shift":instance})
    activityform = ActivityForm(request.POST or None, instance=activityinstance, initial={"shift":instance})
    context["shiftpersonform"] = shiftpersonform
    context["form"] = activityform


    if request.method == 'POST':
        if activityform.is_valid() or shiftpersonform.is_valid():
            if activityform.is_valid():
                activityform.save()
                messages.success(request, 'Activity detail saved ')
            else:
                context["form"] = activityform

            if shiftpersonform.is_valid():
                shiftpersonform.save()
                messages.success(request, 'person detail saved ')
            else:
                context["shiftpersonform"] = shiftpersonform

            return redirect('manpower:shiftdetail', id=id)
        else:
            messages.success(request, 'something gone wrong')
            return redirect('manpower:shiftdetail', id=id)
    else:
        return render(request, "shift/shiftdetail.html", context)
