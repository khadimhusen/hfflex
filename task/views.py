from django.utils import timezone

from django.forms import modelform_factory
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import render, get_object_or_404

from .forms import TaskForm, TaskMsgForm
from .models import Task, TaskMsg
from django.contrib.auth.decorators import login_required
from myproject.access import accessview
from .filters import TaskFilter
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


@login_required(login_url='/login/')
@accessview
def tasklist(request):
    param = request.get_full_path().replace(request.path, "")
    q = request.GET.get('q', None)

    if q != None:
        task_list = Task.objects.filter(state=q)
    else:
        task_list = Task.objects.all()

    myFilter = TaskFilter(request.GET, task_list)
    task_list = myFilter.qs.order_by('target_date').select_related('createdby')

    page = request.GET.get('page', 1)
    paginator = Paginator(task_list, 100)
    try:
        tasks = paginator.page(page)
    except PageNotAnInteger:
        tasks = paginator.page(1)
    except EmptyPage:
        tasks = paginator.page(paginator.num_pages)
    return render(request, 'task/list.html', {'tasks': tasks, 'myFilter': myFilter, 'param': param})


@login_required(login_url='/login/')
@accessview
def addtask(request):
    context = {}
    task_form = TaskForm(request.POST or None)
    context['task_form'] = task_form
    if request.method == "POST":

        if task_form.is_valid():
            task = task_form.save(commit=False)
            task.createdby = request.user
            task.save()
            return HttpResponseRedirect(reverse('task:taskdetail', kwargs={'id': task.id}))
        else:
            context['task_form'] = task_form
    return render(request, "task/addtask.html", context)


@login_required(login_url='/login/')
@accessview
def taskdetail(request, id=None):
    context = {}
    task = get_object_or_404(Task, id=id)
    context['task'] = task
    if task.is_closed == False:
        taskmsgform=TaskMsgForm(request.POST or None,request.FILES or None)
        context['taskmsgform']=taskmsgform
    if request.method == "POST":
        if taskmsgform.is_valid():
            taskmsg=taskmsgform.save(commit=False)
            taskmsg.task=task
            taskmsg.createdby=request.user
            taskmsg.save()
        return HttpResponseRedirect(reverse('task:taskdetail', kwargs={'id': task.id}))
    else:

        if request.user == task.createdby or request.user == task.task_alloted_to:
            request_to_close_form = modelform_factory(Task, fields=('request_to_close',))
            is_closed_form = modelform_factory(Task, fields=('is_closed',))

            if request.user == task.createdby and task.request_to_close == True and task.is_closed==False:
                tocloseform = is_closed_form(instance=task, initial={'is_closed': True})
                context['tocloseform'] = tocloseform
            if task.request_to_close == False and task.is_closed==False:
                requesttocloseform = request_to_close_form(instance=task,
                                                           initial={'request_to_close': True})
                context['requesttocloseform'] = requesttocloseform
        else:
            return HttpResponseRedirect(reverse('task:tasklist'))
    return render(request, "task/detailtask.html", context)


@login_required(login_url='/login/')
@accessview
def toclosetask(request, id=None):
    task = get_object_or_404(Task, id=id)
    is_closed_form = modelform_factory(Task, fields=('is_closed',))

    tocloseform = is_closed_form(request.POST, instance=task)
    if tocloseform.is_valid():
        tasktoclose=tocloseform.save(commit=False)
        tasktoclose.close_date=timezone.now()
        tasktoclose.save()
    return HttpResponseRedirect(reverse('task:taskdetail', kwargs={'id': id}))

@login_required(login_url='/login/')
@accessview
def requesttoclosetask(request, id=None):
    task = get_object_or_404(Task, id=id)
    request_to_close_form = modelform_factory(Task, fields=('request_to_close',))

    requesttocloseform = request_to_close_form(request.POST, instance=task)
    if requesttocloseform.is_valid():
        taskrequest=requesttocloseform.save(commit=False)
        taskrequest.request_date=timezone.now()
        taskrequest.save()
    return HttpResponseRedirect(reverse('task:taskdetail', kwargs={'id': id}))