from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.forms import inlineformset_factory, modelform_factory
from django.shortcuts import render, redirect, get_object_or_404
from manpower.models import Shift, Activity, Machine, ShiftPerson, DowntimeReport
from myproject.access import accessview
from .filters import ShiftFilter, DowntimeFilter, JobQcFilter, ActivityJobFilter
from .forms import NewShiftForm, ActivityForm, ShiftPersonForm , DowntimeReportForm
import datetime
from django.db.models import OuterRef, Subquery, Sum, IntegerField
from django.db.models.functions import Coalesce
from production.models import JobQc

@login_required(login_url='/login/')
@accessview
def shiftlist(request):
    q = request.GET.get('q', None)
    if q != None:
        shift_list = Shift.objects.filter(is_approved=q)
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
            machineinstance = Machine.objects.filter(machinename=user.username).first() or None
            proddate = request.POST['production_date'].split("/")
            if machineinstance:
                proddate = datetime.date(int(proddate[2]), int(proddate[1]), int(proddate[0]))

                obj, created = Shift.objects.get_or_create(
                    shift=request.POST['shift'],
                    machine=machineinstance,
                    production_date=proddate,
                )
                if created:
                    Shift.objects.filter(id=obj.id).update(createdby=user)

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
def shiftdetail(request, id=None):
    context = {}
    instance = get_object_or_404(Shift, id=id)
    context["instance"] = instance
    qperson = request.GET.get('qperson', None)
    qactivity = request.GET.get('qactivity', None)
    activityinstance = None
    personinstance = None
    context["downtimeform"] = None
    downtimeform = None

    if qperson:
        personinstance = get_object_or_404(ShiftPerson, id=qperson)

    if qactivity:
        activityinstance = get_object_or_404(Activity, id=qactivity)
        downtimeformset = inlineformset_factory(Activity, model=DowntimeReport, form=DowntimeReportForm,
                                                extra=2, can_delete=True)
        downtimeform = downtimeformset(request.POST or None, instance=activityinstance)
        context["downtimeform"] = downtimeform

    personform = ShiftPersonForm
    shiftpersonform = personform(request.POST or None, instance=personinstance, initial={"shift": instance})
    activityform = ActivityForm(request.POST or None, instance=activityinstance, initial={"shift": instance})

    context["shiftpersonform"] = shiftpersonform
    context["form"] = activityform

    if request.method == 'POST':
        if activityform.is_valid() or shiftpersonform.is_valid():
            if downtimeform:
                if downtimeform.is_valid():
                    print(downtimeform)
                    downtimeform.save()
                    messages.success(request, 'down time saved detail saved ')
                else:
                    print(downtimeform)
                    print(downtimeform.errors)
                    context["downtimeform"] = downtimeform
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
            print("activity form ",activityform.errors)
            messages.success(request, 'something gone wrong')
            return redirect('manpower:shiftdetail', id=id)
    else:
        return render(request, "shift/shiftdetail.html", context)


def approveshift(request, id=None):
    if request.method=='POST':
       Shift.objects.filter(id=id).update(is_approved=True)
    return redirect('manpower:shiftdetail',id=id)

@login_required(login_url='/login/')
@accessview
def downtimelist(request):
    machine=request.GET.get('machine', None)
    q = request.GET.get('q', None)
    if q != None:
        downtime_list = DowntimeReport.objects.filter(is_approved=q)
    else:
        downtime_list = DowntimeReport.objects.all()

    myFilter = DowntimeFilter(request.GET, downtime_list)
    downtime_list = myFilter.qs
    page = request.GET.get('page', 1)
    paginator = Paginator(downtime_list, 100)
    try:
        downtimes = paginator.page(page)
    except PageNotAnInteger:
        downtimes = paginator.page(1)
    except EmptyPage:
        downtimes = paginator.page(paginator.num_pages)

    return render(request, 'activity/downtimelist.html', {"downtimes": downtimes,
                                                          'myFilter': myFilter,'machine':machine })



@login_required(login_url='/login/')
@accessview
def qctestlist(request):

    qc_list = JobQc.objects.all().order_by('created')

    myFilter = JobQcFilter(request.GET, qc_list)
    qc_list = myFilter.qs
    page = request.GET.get('page', 1)
    paginator = Paginator(qc_list, 100)
    try:
        qc_list = paginator.page(page)
    except PageNotAnInteger:
        qc_list = paginator.page(1)
    except EmptyPage:
        qc_list = paginator.page(paginator.num_pages)

    return render(request, 'activity/qclist.html', {"qclist": qc_list,
                                                          'myFilter': myFilter})


@login_required(login_url='/login/')
@accessview
def joblist(request):
    """Every job worked on in a shift (one row per Activity), filterable by
    job / item / customer / machine / shift / date -- with page-wide totals
    for the filtered set, same shape as the other manpower lists."""
    # One downtime total per activity in the query itself, instead of the
    # Activity.totaldowntime property running a query for every row.
    downtime_sq = (DowntimeReport.objects.filter(activity=OuterRef('pk'))
                   .values('activity').annotate(total=Sum('downtime')).values('total'))
    activity_list = (Activity.objects
                     .select_related('shift', 'shift__machine', 'jobid', 'jobid__joborder__customer')
                     .annotate(downtime_total=Coalesce(Subquery(downtime_sq, output_field=IntegerField()), 0))
                     .order_by('-shift__production_date', '-shift__id', '-id'))

    myFilter = ActivityJobFilter(request.GET, activity_list)
    activity_list = myFilter.qs

    totals = activity_list.aggregate(
        qty=Sum('qty'), rolls=Sum('rolls'), lot=Sum('lot'), tag=Sum('tag'),
        totaltime=Sum('totaltime'), downtime=Sum('downtime_total'),
    )

    page = request.GET.get('page', 1)
    paginator = Paginator(activity_list, 100)
    try:
        activities = paginator.page(page)
    except PageNotAnInteger:
        activities = paginator.page(1)
    except EmptyPage:
        activities = paginator.page(paginator.num_pages)

    return render(request, 'activity/joblist.html', {"activities": activities,
                                                     'myFilter': myFilter,
                                                     'totals': totals})
