"""Overdue tasks lock the person they are assigned to.

A task may be overdue only so long, depending on its priority:

    HIGH 2 days, NORMAL 3 days, LOW 6 days

Past that the assignee can do nothing in the system until the person who allotted the task
(its creator) gives it a new target date. A locked user still gets to: the lock page, the
task pages (to read it, chat with the creator, ask for a new date, or ask to close it),
notifications and logout. Everything else is sent to the lock page.

A task the user allotted to themselves locks them just the same: they have to give it a new
date themselves (the lock page offers that straight away).

Not locked by a task: one they have already asked to close (the creator has to act), one with
nobody recorded as having allotted it (nobody could change its date), a closed one."""
import re
import time as time_module
from datetime import date as date_type, datetime, time, timedelta

from django.db.models import Q
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse

from .models import Task

LIMIT_DAYS = {'HIGH': 2, 'NORMAL': 3, 'LOW': 6}
CACHE_SECONDS = 60                       # how long "nothing is locked" is trusted per session
SESSION_KEY = 'task_lock_clear_until'

# What a locked user can still reach.
ALLOWED_PATHS = [re.compile(pattern) for pattern in (
    r'^/(login|logout)/', r'^/(static|media)/',
    r'^/task/locked/$', r'^/task/detail/\d+/$', r'^/task/message/\d+/$',
    r'^/task/requesttoclose/\d+/$', r'^/task/toclosetask/\d+/$',
    r'^/task/changedate/\d+/$', r'^/task/askdate/\d+/$',
    r'^/task/notifications/read/$', r'^/task/pending-json/$',
    r'^/api/task/', r'^/api/crm/me/$',
)]


def limit_for(priority):
    """Days a task of this priority may be overdue (an unknown priority counts as LOW)."""
    return LIMIT_DAYS.get(priority, LIMIT_DAYS['LOW'])


def days_overdue(task, today=None):
    """Whole days past the target date; zero or less when it is not overdue."""
    return ((today or date_type.today()) - task.target_date.date()).days


def is_locking(task, today=None):
    """Does this task lock its assignee right now?"""
    return (not task.is_closed and not task.request_to_close and task.createdby_id is not None
            and days_overdue(task, today) > limit_for(task.priority))


def _too_late(today):
    """Tasks overdue by more than their priority allows."""
    cutoff = lambda days: datetime.combine(today - timedelta(days=days), time.min)
    condition = Q()
    for priority, days in LIMIT_DAYS.items():
        condition |= Q(priority=priority, target_date__lt=cutoff(days))
    condition |= ~Q(priority__in=list(LIMIT_DAYS)) & Q(target_date__lt=cutoff(LIMIT_DAYS['LOW']))
    return condition


def _candidates():
    return Task.objects.filter(is_closed=False, request_to_close=False, createdby__isnull=False)


def locked_tasks(user, today=None):
    """The user's tasks that lock them."""
    return _candidates().filter(_too_late(today or date_type.today()), task_alloted_to=user).order_by('target_date', 'id')


def tasks_to_unlock(user, today=None):
    """Tasks this user allotted to somebody else that now lock them: the ones whose date needs changing.
    (Ones they allotted to themselves are in locked_tasks, with the date form right there.)"""
    return (_candidates().filter(_too_late(today or date_type.today()), createdby=user)
            .exclude(task_alloted_to=user).order_by('target_date', 'id'))


def describe(task, today=None):
    """How far over the limit a task is, for the screens."""
    return {'task': task, 'days': days_overdue(task, today), 'limit': limit_for(task.priority),
            'own': task.createdby_id == task.task_alloted_to_id}      # allotted to themselves: they set the date


# ---- the gate -----------------------------------------------------------------------

def is_allowed(path):
    return any(pattern.match(path) for pattern in ALLOWED_PATHS)


def lock_response(request, today=None):
    """None when the request may go on; otherwise the response that stops it (a redirect to the
    lock page, or a 403 for scripts and the API)."""
    user = request.user
    if not user.is_authenticated or is_allowed(request.path):
        return None
    session = request.session
    if session.get(SESSION_KEY, 0) > time_module.time():
        return None
    if not locked_tasks(user, today).exists():
        if CACHE_SECONDS:
            session[SESSION_KEY] = time_module.time() + CACHE_SECONDS
        return None
    session.pop(SESSION_KEY, None)                  # never trust "clear" right after being locked
    url = reverse('task:locked')
    if (request.path.startswith('/api/') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or request.content_type == 'application/json'):
        return JsonResponse({'detail': 'You have tasks overdue beyond their limit. Ask whoever allotted them '
                                       'to change the target date.', 'code': 'tasks_locked', 'url': url}, status=403)
    return HttpResponseRedirect(url)
