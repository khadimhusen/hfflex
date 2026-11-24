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
from . import lock, popup
from datetime import date as date_type, datetime, timedelta
from django.utils.dateparse import parse_date, parse_datetime
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
    # While the user is going through their due tasks (the pop-up after login), a due task
    # offers "Later" so they can move on to the next one.
    context['show_later'] = popup.can_postpone(request.user, request.session, task)
    # A task overdue past its limit locks its assignee until the creator gives it a new date.
    if request.user == task.task_alloted_to and lock.is_locking(task):
        context['lock_info'] = lock.describe(task)
    context['can_change_date'] = request.user == task.createdby and not task.is_closed
    context['creator_sees_locked'] = (context['can_change_date'] and lock.is_locking(task)
                                      and task.createdby_id != task.task_alloted_to_id)
    if context['can_change_date']:
        context['target_input'] = task.target_date.strftime('%Y-%m-%dT%H:%M')

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
def task_later(request, id):
    """Put a due task off for now. From the pop-up (AJAX) it just answers with how many due
    tasks are left; from the task's own page it goes on to the job list, where the pop-up
    shows the ones still left (or nothing, when that was the last)."""
    task = get_object_or_404(Task, id=id, task_alloted_to=request.user, is_closed=False)
    ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if not popup.is_due(task) or lock.is_locking(task):
        reason = ('This task is overdue past its limit: ask for a new target date.' if lock.is_locking(task)
                  else 'This task is not due yet.')
        if ajax:
            return JsonResponse({'error': reason}, status=400)
        messages.error(request, reason)
        return HttpResponseRedirect(reverse('task:taskdetail', kwargs={'id': id}))
    remaining = popup.postpone(request.user, request.session, task)
    if ajax:
        return JsonResponse({'remaining': remaining})
    if not remaining:
        messages.success(request, 'You have been through all your due tasks.')
    # The job list shows the pop-up by itself while due tasks are left, so no flag is needed.
    return HttpResponseRedirect(reverse('order:joblist'))


ASK_TEXT = 'Please change the target date of this task.'


def _person(user):
    return (user.get_full_name().strip() or user.username) if user else ''


def _safe_next(request, fallback):
    """Where to go back to: only the lock page or a task page, never an outside address."""
    target = request.POST.get('next', '')
    return target if target == reverse('task:locked') or target.startswith('/task/detail/') else fallback


def _parse_target(text, current):
    """A new target date from the form: date and time, or just a date (keeping the old time)."""
    text = (text or '').strip().replace(' ', 'T')
    try:
        when = parse_datetime(text) if 'T' in text else None
        if when is None:
            day = parse_date(text)
            when = datetime.combine(day, current.time()) if day else None
    except ValueError:                       # well-formed but impossible, like 2030-13-45
        return None
    return when.replace(tzinfo=None, second=0, microsecond=0) if when else None


@login_required(login_url='/login/')
def task_locked(request):
    """Shown to a user locked by overdue tasks: which ones, who allotted them, and (for tasks
    this user allotted to others that are locked) where to change the date."""
    mine = [lock.describe(t) for t in lock.locked_tasks(request.user).select_related('createdby')]
    to_fix = [lock.describe(t) for t in lock.tasks_to_unlock(request.user).select_related('task_alloted_to')]
    if not mine and not to_fix:
        return HttpResponseRedirect(reverse('order:joblist'))
    return render(request, 'task/locked.html', {
        'locked': mine, 'to_fix': to_fix, 'is_locked': bool(mine),
        'recent_asks': set(TaskMsg.objects.filter(
            createdby=request.user, msg_text__startswith=ASK_TEXT,
            created__gte=datetime.now() - timedelta(hours=1)).values_list('task_id', flat=True)),
        'next': reverse('task:locked'),
    })


@login_required(login_url='/login/')
@require_POST
def change_target_date(request, id):
    """The person who created (allotted) a task can give it a new target date, whoever it is
    assigned to: it also frees the assignee if the task had locked them. It is noted in the task
    chat and the assignee is told (unless the creator gave the task to themselves)."""
    task = get_object_or_404(Task, id=id)
    back = _safe_next(request, reverse('task:taskdetail', kwargs={'id': id}))
    if request.user != task.createdby:
        messages.error(request, 'Only the person who allotted this task can change its target date.')
        return HttpResponseRedirect(reverse('task:taskdetail', kwargs={'id': id}))
    if task.is_closed:
        messages.error(request, 'This task is closed.')
        return HttpResponseRedirect(back)
    new = _parse_target(request.POST.get('target_date'), task.target_date)
    if new is None:
        messages.error(request, 'Give a valid target date.')
        return HttpResponseRedirect(back)
    if new.date() < date_type.today():
        messages.error(request, 'The new target date cannot be in the past.')
        return HttpResponseRedirect(back)
    old = task.target_date
    task.target_date = new
    task.editedby = request.user
    task.save()
    note = f'Target date changed from {old:%d/%m/%Y %H:%M} to {new:%d/%m/%Y %H:%M} by {_person(request.user)}.'
    TaskMsg.objects.create(task=task, msg_text=note, createdby=request.user)
    if task.task_alloted_to_id != request.user.pk:
        create_notification(task.task_alloted_to, task,
                            f'{_person(request.user)} changed the target date of "{task.taskname}" to {new:%d/%m/%Y}.')
    messages.success(request, f'Target date changed to {new:%d/%m/%Y %H:%M}.')
    return HttpResponseRedirect(back)


@login_required(login_url='/login/')
@require_POST
def ask_date_change(request, id):
    """The assignee of an overdue task asks whoever allotted it for a new target date: a message
    in the task chat plus a notification. Once an hour per task is plenty."""
    task = get_object_or_404(Task, id=id, task_alloted_to=request.user, is_closed=False)
    back = _safe_next(request, reverse('task:taskdetail', kwargs={'id': id}))
    creator = task.createdby
    if creator is None or creator == request.user:
        messages.error(request, 'There is nobody else to ask: you allotted this task yourself.')
        return HttpResponseRedirect(back)
    if TaskMsg.objects.filter(task=task, createdby=request.user, msg_text__startswith=ASK_TEXT,
                              created__gte=datetime.now() - timedelta(hours=1)).exists():
        messages.info(request, f'You already asked {_person(creator)}. Please wait for the new date.')
        return HttpResponseRedirect(back)
    days = max(lock.days_overdue(task), 0)
    TaskMsg.objects.create(task=task, createdby=request.user,
                           msg_text=f'{ASK_TEXT} It is {days} day(s) overdue and I cannot continue until it changes.')
    create_notification(creator, task, f'{_person(request.user)} asks you to change the target date of '
                                       f'"{task.taskname}" ({days} day(s) overdue).')
    messages.success(request, f'{_person(creator)} has been asked to change the target date.')
    return HttpResponseRedirect(back)


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
    ).select_related('task_alloted_to').order_by('day_of_month')
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