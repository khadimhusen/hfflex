from django.utils import timezone
from django.forms import modelform_factory
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Q
from .forms import TaskForm, TaskMsgForm
from .models import Task, TaskMsg, Notification
from django.contrib.auth.decorators import login_required
from myproject.access import accessview
from .filters import TaskFilter
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


def create_notification(user, task, message):
    Notification.objects.create(user=user, task=task, message=message)


@login_required(login_url='/login/')
@accessview
def tasklist(request):
    param = request.get_full_path().replace(request.path, "")
    tab = request.GET.get('tab', 'assigned')

    all_tasks = Task.objects.select_related('createdby', 'task_alloted_to')

    if tab == 'assigned':
        task_list = all_tasks.filter(task_alloted_to=request.user, is_closed=False)
    elif tab == 'created':
        task_list = all_tasks.filter(createdby=request.user, is_closed=False)
    elif tab == 'toclose':
        task_list = all_tasks.filter(createdby=request.user, is_closed=False, request_to_close=True)
    else:
        task_list = all_tasks.filter(Q(task_alloted_to=request.user) | Q(createdby=request.user))

    myFilter = TaskFilter(request.GET, task_list)
    task_list = myFilter.qs.order_by('target_date')

    page = request.GET.get('page', 1)
    paginator = Paginator(task_list, 100)
    try:
        tasks = paginator.page(page)
    except PageNotAnInteger:
        tasks = paginator.page(1)
    except EmptyPage:
        tasks = paginator.page(paginator.num_pages)

    return render(request, 'task/list.html', {
        'tasks': tasks,
        'myFilter': myFilter,
        'param': param,
        'tab': tab,
    })


@login_required(login_url='/login/')
@accessview
def addtask(request):
    task_form = TaskForm(request.POST or None)
    if request.method == "POST":
        if task_form.is_valid():
            task = task_form.save(commit=False)
            task.createdby = request.user
            task.save()
            # notify assignee
            if task.task_alloted_to != request.user:
                create_notification(
                    task.task_alloted_to, task,
                    f'New task assigned to you: "{task.taskname}"'
                )
            messages.success(request, f'Task "{task.taskname}" created successfully.')
            return HttpResponseRedirect(reverse('task:taskdetail', kwargs={'id': task.id}))
    return render(request, "task/addtask.html", {'task_form': task_form})


@login_required(login_url='/login/')
@accessview
def taskdetail(request, id=None):
    context = {}
    task = get_object_or_404(Task, id=id)

    # access check
    if request.user != task.createdby and request.user != task.task_alloted_to:
        messages.error(request, "You don't have access to this task.")
        return HttpResponseRedirect(reverse('task:tasklist'))

    context['task'] = task

    if not task.is_closed:
        context['taskmsgform'] = TaskMsgForm()

    if request.user == task.createdby and task.request_to_close and not task.is_closed:
        tocloseform = modelform_factory(Task, fields=('is_closed',))
        context['tocloseform'] = tocloseform(instance=task, initial={'is_closed': True})

    if not task.request_to_close and not task.is_closed:
        requesttocloseform = modelform_factory(Task, fields=('request_to_close',))
        context['requesttocloseform'] = requesttocloseform(
            instance=task, initial={'request_to_close': True}
        )

    return render(request, "task/detailtask.html", context)


@login_required(login_url='/login/')
@require_POST
def post_task_message(request, id):
    task = get_object_or_404(Task, id=id)
    if request.user != task.createdby and request.user != task.task_alloted_to:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    if task.is_closed:
        return JsonResponse({'success': False, 'error': 'Task is closed'}, status=400)

    form = TaskMsgForm(request.POST, request.FILES)
    if form.is_valid():
        msg = form.save(commit=False)
        msg.task = task
        msg.createdby = request.user
        msg.save()

        # notify the other party
        notify_user = task.createdby if request.user == task.task_alloted_to else task.task_alloted_to
        create_notification(
            notify_user, task,
            f'New message on task "{task.taskname}" from {request.user}'
        )

        thumbnail_url = msg.thumbnail.url if msg.thumbnail else None
        image_url = msg.msg_image.url if msg.msg_image else None
        file_url = msg.msg_file.url if msg.msg_file else None
        file_name = msg.msg_file.name if msg.msg_file else None

        return JsonResponse({
            'success': True,
            'msg_id': msg.id,
            'msg_text': msg.msg_text or '',
            'createdby': str(msg.createdby),
            'created': msg.created.strftime('%d/%m/%Y %H:%M'),
            'image_url': image_url,
            'thumbnail_url': thumbnail_url,
            'file_url': file_url,
            'file_name': file_name,
        })
    return JsonResponse({'success': False, 'errors': form.errors}, status=400)


@login_required(login_url='/login/')
@accessview
def toclosetask(request, id=None):
    task = get_object_or_404(Task, id=id)
    if request.user != task.createdby:
        messages.error(request, "Only the task creator can close this task.")
        return HttpResponseRedirect(reverse('task:taskdetail', kwargs={'id': id}))

    is_closed_form = modelform_factory(Task, fields=('is_closed',))
    tocloseform = is_closed_form(request.POST, instance=task)
    if tocloseform.is_valid():
        t = tocloseform.save(commit=False)
        t.close_date = timezone.now()
        t.save()
        create_notification(
            task.task_alloted_to, task,
            f'Task "{task.taskname}" has been closed by {request.user}.'
        )
        messages.success(request, f'Task "{task.taskname}" closed successfully.')
    return HttpResponseRedirect(reverse('task:taskdetail', kwargs={'id': id}))


@login_required(login_url='/login/')
@accessview
def requesttoclosetask(request, id=None):
    task = get_object_or_404(Task, id=id)
    request_to_close_form = modelform_factory(Task, fields=('request_to_close',))
    requesttocloseform = request_to_close_form(request.POST, instance=task)
    if requesttocloseform.is_valid():
        t = requesttocloseform.save(commit=False)
        t.request_date = timezone.now()
        t.save()
        create_notification(
            task.createdby, task,
            f'{request.user} requested to close task "{task.taskname}".'
        )
        messages.success(request, 'Close request sent to task creator.')
    return HttpResponseRedirect(reverse('task:taskdetail', kwargs={'id': id}))


@login_required(login_url='/login/')
def mark_notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True})


@login_required(login_url='/login/')
def pending_tasks_json(request):
    tasks = Task.objects.filter(
        task_alloted_to=request.user,
        is_closed=False
    ).select_related('createdby').order_by('target_date').values(
        'id', 'taskname', 'priority',
        'target_date', 'createdby__username'
    )
    return JsonResponse({'tasks': list(tasks)})


from .models import Task, TaskMsg, Notification, RecurringTask
from .forms import TaskForm, TaskMsgForm, RecurringTaskForm

@login_required(login_url='/login/')
@accessview
def recurring_task_list(request):
    recurring = RecurringTask.objects.filter(
        createdby=request.user
    ).select_related('task_alloted_to').order_by('next_due_date')
    return render(request, 'task/recurring_list.html', {'recurring': recurring})


@login_required(login_url='/login/')
@accessview
def recurring_task_add(request):
    form = RecurringTaskForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        r = form.save(commit=False)
        r.createdby = request.user
        r.save()
        messages.success(request, f'Recurring task "{r.taskname}" created.')
        return HttpResponseRedirect(reverse('task:recurring_list'))
    return render(request, 'task/recurring_add.html', {'form': form})


@login_required(login_url='/login/')
@accessview
def recurring_task_edit(request, id):
    r = get_object_or_404(RecurringTask, id=id, createdby=request.user)
    form = RecurringTaskForm(request.POST or None, instance=r)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Updated "{r.taskname}".')
        return HttpResponseRedirect(reverse('task:recurring_list'))
    return render(request, 'task/recurring_add.html', {'form': form, 'edit': True})


@login_required(login_url='/login/')
@accessview
def recurring_task_toggle(request, id):
    r = get_object_or_404(RecurringTask, id=id, createdby=request.user)
    r.is_active = not r.is_active
    r.save()
    status = 'activated' if r.is_active else 'paused'
    messages.success(request, f'Recurring task "{r.taskname}" {status}.')
    return HttpResponseRedirect(reverse('task:recurring_list'))