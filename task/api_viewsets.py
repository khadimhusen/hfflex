from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from .api_serializers import (
    NotificationSerializer, RecurringTaskSerializer, TaskMsgSerializer, TaskSerializer, UserLookupSerializer,
)
from .models import Notification, RecurringTask, Task, TaskMsg
from .permissions import IsTaskUser


class UserLookupViewSet(viewsets.ReadOnlyModelViewSet):
    """For the assignee dropdown on the task create/edit form."""
    serializer_class = UserLookupSerializer
    permission_classes = [IsTaskUser]
    queryset = User.objects.filter(is_active=True).order_by('first_name', 'username')


class TaskViewSet(viewsets.ModelViewSet):
    """Mirrors tasklist/addtask/taskdetail/toclosetask/requesttoclosetask.
    No department gate -- task views were login_required only. ?tab=
    matches the old view's own tab param (assigned/created/toclose/all),
    defaulting to 'assigned' like the old view did.

    TaskMsg (the per-task comment/attachment thread) and RecurringTask are
    their own viewsets below."""
    queryset = Task.objects.select_related('createdby', 'task_alloted_to').order_by('target_date')
    serializer_class = TaskSerializer
    permission_classes = [IsTaskUser]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        # The ?tab= filter only makes sense for the list view -- it's the
        # tab strip's own filtering, not an access rule. Detail actions
        # (retrieve/update/destroy/close/request_close) must see every task
        # the user has any relationship to, closed or not, or e.g. closing
        # a task the *creator* isn't also assigned to -- or even just
        # reopening the detail page after it's been closed -- 404s despite
        # get_object()'s explicit check below allowing it.
        if self.action != 'list':
            return qs.filter(Q(task_alloted_to=user) | Q(createdby=user))
        tab = self.request.query_params.get('tab', 'assigned')
        if tab == 'assigned':
            qs = qs.filter(task_alloted_to=user, is_closed=False)
        elif tab == 'created':
            qs = qs.filter(createdby=user, is_closed=False)
        elif tab == 'toclose':
            qs = qs.filter(createdby=user, is_closed=False, request_to_close=True)
        elif tab == 'all':
            qs = qs.filter(Q(task_alloted_to=user) | Q(createdby=user))
        return qs

    def get_object(self):
        # Mirrors taskdetail()'s access check -- applies to every detail
        # action below (retrieve/update/destroy/close/request_close) since
        # they all route through get_object().
        obj = super().get_object()
        if self.request.user != obj.createdby and self.request.user != obj.task_alloted_to:
            raise PermissionDenied("You don't have access to this task.")
        return obj

    def perform_create(self, serializer):
        task = serializer.save(createdby=self.request.user)
        if task.task_alloted_to_id != self.request.user.id:
            Notification.objects.create(
                user=task.task_alloted_to, task=task,
                message=f'New task assigned to you: "{task.taskname}"',
            )

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        task = self.get_object()
        if request.user != task.createdby:
            raise PermissionDenied('Only the task creator can close this task.')
        task.is_closed = True
        task.close_date = timezone.now()
        task.save(update_fields=['is_closed', 'close_date'])
        Notification.objects.create(
            user=task.task_alloted_to, task=task,
            message=f'Task "{task.taskname}" has been closed by {request.user}.',
        )
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=['post'], url_path='request-close')
    def request_close(self, request, pk=None):
        task = self.get_object()
        task.request_to_close = True
        task.request_date = timezone.now()
        task.save(update_fields=['request_to_close', 'request_date'])
        Notification.objects.create(
            user=task.createdby, task=task,
            message=f'{request.user} requested to close task "{task.taskname}".',
        )
        return Response(self.get_serializer(task).data)

    @action(detail=False, methods=['get'], url_path='nav-summary')
    def nav_summary(self, request):
        """Mirrors tasklist()'s taskteome/taskbyme/tasktobeclose counts."""
        user = request.user
        return Response({
            'assigned_to_me': Task.objects.filter(task_alloted_to=user, is_closed=False).count(),
            'created_by_me': Task.objects.filter(createdby=user, is_closed=False).count(),
            'to_close': Task.objects.filter(createdby=user, is_closed=False, request_to_close=True).count(),
        })


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Read-only -- notifications are only ever created server-side by
    TaskViewSet's own actions, never directly by the client."""
    queryset = Notification.objects.select_related('task').order_by('-created')
    serializer_class = NotificationSerializer
    permission_classes = [IsTaskUser]

    def get_queryset(self):
        qs = super().get_queryset().filter(user=self.request.user)
        if self.request.query_params.get('unread') == 'true':
            qs = qs.filter(is_read=False)
        return qs

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'success': True})


class TaskMsgViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Mirrors detailtask's chat pane + post_task_message. Always scoped to
    one task via a required `task` id (query param for list, form field for
    create) -- both go through the same createdby/task_alloted_to access
    check as TaskViewSet.get_object()."""
    queryset = TaskMsg.objects.select_related('createdby').filter(is_deleted=False).order_by('created')
    serializer_class = TaskMsgSerializer
    permission_classes = [IsTaskUser]

    def _get_task(self):
        task_id = self.request.query_params.get('task') or self.request.data.get('task')
        if not task_id:
            raise ValidationError({'task': 'This field is required.'})
        task = get_object_or_404(Task, id=task_id)
        if self.request.user != task.createdby and self.request.user != task.task_alloted_to:
            raise PermissionDenied("You don't have access to this task.")
        return task

    def get_queryset(self):
        return super().get_queryset().filter(task=self._get_task())

    def perform_create(self, serializer):
        task = self._get_task()
        if task.is_closed:
            raise ValidationError({'task': 'This task is closed.'})
        msg = serializer.save(task=task, createdby=self.request.user)
        notify_user = task.createdby if self.request.user == task.task_alloted_to else task.task_alloted_to
        Notification.objects.create(
            user=notify_user, task=task,
            message=f'New message on task "{task.taskname}" from {self.request.user}',
        )


class RecurringTaskViewSet(viewsets.ModelViewSet):
    """Mirrors recurring_task_list/add/edit/toggle -- always scoped to the
    creator, same as the old views' createdby=request.user filter."""
    queryset = RecurringTask.objects.select_related('task_alloted_to', 'createdby').order_by('day_of_month')
    serializer_class = RecurringTaskSerializer
    permission_classes = [IsTaskUser]

    def get_queryset(self):
        return super().get_queryset().filter(createdby=self.request.user)

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    @action(detail=True, methods=['post'])
    def toggle(self, request, pk=None):
        r = self.get_object()
        r.is_active = not r.is_active
        r.save(update_fields=['is_active'])
        return Response(self.get_serializer(r).data)
