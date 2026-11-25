"""The due-task review and the overdue lock, for the frontend (the old pages do the same through
task/views.py and the job list; the rules are in popup.py, lock.py and date_change.py).

    GET  /api/task/review/              what to show now: the pop-up's tasks, and the lock state
    POST /api/task/review/later/<id>/   put a due task off

GET takes ?fresh=1 right after a login: that starts the review (the old pages do it at login)."""
from datetime import datetime, timedelta

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from . import date_change, lock, popup
from .models import Task, TaskMsg
from .permissions import IsTaskUser


def task_row(task, today=None):
    """One task as the pop-up and the lock screen show it."""
    return {
        'id': task.id,
        'taskname': task.taskname,
        'target_date': task.target_date.isoformat(),
        'priority': task.priority,
        'createdby': task.createdby_id,
        'createdby_name': date_change.person(task.createdby),
        'task_alloted_to': task.task_alloted_to_id,
        'task_alloted_to_name': date_change.person(task.task_alloted_to),
        'is_due': popup.is_due(task, today),
        'days_overdue': max(lock.days_overdue(task, today), 0),
        'limit_days': lock.limit_for(task.priority),
        'locks': lock.is_locking(task, today),           # past its limit: no Later, the date must change
        'own': task.createdby_id == task.task_alloted_to_id,
    }


def recent_asks(user):
    """Tasks this user already asked for a new date on, within the last hour."""
    return list(TaskMsg.objects.filter(
        createdby=user, msg_text__startswith=date_change.ASK_TEXT,
        created__gte=datetime.now() - timedelta(hours=1)).values_list('task_id', flat=True).distinct())


class ReviewView(APIView):
    permission_classes = [IsTaskUser]

    def get(self, request):
        user = request.user
        if request.query_params.get('fresh'):
            request.session['show_pending_tasks'] = True
        mine = [task_row(t) for t in lock.locked_tasks(user).select_related('createdby', 'task_alloted_to')]
        to_fix = [task_row(t) for t in lock.tasks_to_unlock(user).select_related('createdby', 'task_alloted_to')]
        # A locked user gets the lock screen, not the pop-up (the pop-up waits until they are free).
        tasks = [] if mine else [task_row(t) for t in popup.popup_for_request(request)]
        return Response({
            'show': bool(tasks),
            'tasks': tasks,
            'due_left': sum(1 for t in tasks if t['is_due']),
            'locked': bool(mine),
            'locked_tasks': mine,
            'to_fix': to_fix,
            'recent_asks': recent_asks(user),
        })


class LaterView(APIView):
    permission_classes = [IsTaskUser]

    def post(self, request, pk):
        task = get_object_or_404(Task, id=pk, task_alloted_to=request.user, is_closed=False)
        if lock.is_locking(task):
            return Response({'detail': 'This task is overdue past its limit: ask for a new target date.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not popup.is_due(task):
            return Response({'detail': 'This task is not due yet.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'remaining': popup.postpone(request.user, request.session, task)})
