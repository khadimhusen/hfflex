from django import template
from django.db.models import Sum
from django.conf import settings

from preorder.models import JobName
from purchase.models import Po
from task.models import Task
from employee.models import Department

register = template.Library()

from ..models import Job


@register.simple_tag
def pendingjobs():
    return Job.objects.filter(jobstatus="Pending").count()


@register.simple_tag
def jobwork():
    return Job.objects.filter(jobstatus="Job Work").count()


@register.simple_tag
def partiallyready():
    return Job.objects.filter(jobstatus="Partially Ready").count()


@register.simple_tag
def prejob():
    return JobName.objects.filter(job__isnull=True, preorder__final_submition=True)


@register.inclusion_tag('prejoblist.html')
def prejoblist():
    jobs = JobName.objects.filter(job__isnull=True, preorder__final_submition=True)
    joblist = []

    for job in jobs:
        joblist.append({"jobname": job.jobname, "qty": job.qty, "customer": job.preorder.customer})

    return {'joblist': joblist, 'jobcount': jobs.count()}


@register.simple_tag
def newjobs():
    return Job.objects.filter(jobstatus="Unplanned").count()

@register.simple_tag
def accountclearance():
    return Job.objects.filter(jobstatus="Account clearance").count()

@register.simple_tag
def pendingkg():
    result = Job.objects.filter(jobstatus="Pending").aggregate(Sum('kgqty'))
    return result['kgqty__sum'] or 0


@register.simple_tag
def accountclearancekg():
    result = Job.objects.filter(jobstatus="Account clearance").aggregate(Sum('kgqty'))
    return round(result['kgqty__sum'] or 0)

@register.simple_tag
def newkg():
    result = Job.objects.filter(jobstatus="Unplanned").aggregate(Sum('kgqty'))
    return round(result['kgqty__sum'] or 0)


@register.filter(name='abs')
def abs_filter(value=0):
    return abs(value)


@register.filter(name='choices_item')
def index_filter(value, i):
    return value[i - 1][1]


@register.simple_tag
def base_url():
    return settings.DOMAINO


@register.inclusion_tag('purchase_approval_pending.html')
def polist():
    pos = Po.objects.filter(approvedby__isnull=True).exclude(status="Hold")
    pendingpos = Po.objects.filter(approvedby__isnull=False).exclude(status__in=["Completed",
                                                                                 "Hold",
                                                                                 "Cancelled"
                                                                                 ]).order_by("delivery_date")
    polist = []
    pendingpolist = []

    for po in pos:
        polist.append({"id": po.id, "party": po.supplier, "date": po.created, "createdby": po.createdby})

    for po in pendingpos:
        pendingpolist.append({"id": po.id, "party": po.supplier, "date": po.approve_date, "createdby": po.approvedby})

    return {'polist': polist, 'pocount': pos.count(), 'pendingpocount': pendingpos.count(),
            'pendingpolist': pendingpolist}


@register.inclusion_tag('task.html', takes_context=True)
def tasklist(context):
    request = context['request']  # Get the request from the context
    user = request.user
    userid=user.id

    tasktome = Task.objects.filter(task_alloted_to=user, is_closed=False).count()
    taskbyme = Task.objects.filter(createdby=user, is_closed=False).count()
    tasktobeclose = Task.objects.filter(createdby=user, is_closed=False, request_to_close=True).count()

    return {'taskteome': tasktome, 'taskbyme': taskbyme, 'tasktobeclose': tasktobeclose,'userid':userid}


@register.filter
def user_in_department(user, department_name):
    try:
        department = Department.objects.get(department_name=department_name)
        return department.user.filter(id=user.id).exists()
    except Department.DoesNotExist:
        return False