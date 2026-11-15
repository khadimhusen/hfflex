"""What happens to a meeting's action items: each one becomes a real Task for its
owner when the meeting is finalised (so it shows up in their tasks with the usual
notification), and stays in step with that task afterwards."""
from datetime import datetime, time

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from task.models import Notification, Task

from . import richtext

DUE_TIME = time(18, 0)          # a task's target is a date and time; items only have a due day


def _task_fields(item):
    meeting = item.meeting
    return dict(
        taskname=f'{meeting.number}: {item.description}'[:256],
        description=(f'Action item from the meeting "{meeting.title}" ({meeting.number}), '
                     f'held on {meeting.meeting_date:%d/%m/%Y}.\n\n{item.description}'),
        target_date=datetime.combine(item.due_date, DUE_TIME),
        priority=item.priority,
        task_alloted_to=item.owner,
    )


def _notify(user, task, message):
    Notification.objects.create(user=user, task=task, message=message[:512])


def create_task_for(item, actor):
    """Make the owner's task for `item` (once). The meeting's creator is the task's
    creator, so they are the one who confirms it closed."""
    if item.task_id:
        return item.task
    creator = item.meeting.created_by or actor
    task = Task.objects.create(createdby=creator, **_task_fields(item))
    item.task = task
    item.save(update_fields=['task'])
    if item.owner_id != creator.id:
        _notify(item.owner, task, f'New action item from {item.meeting.number}: "{item.description}"')
    return task


def sync_task(item, actor):
    """After an action item is edited: carry the change to its task, unless the
    task is already closed."""
    task = item.task
    if task is None or task.is_closed:
        return
    previous_owner = task.task_alloted_to_id
    for field, value in _task_fields(item).items():
        setattr(task, field, value)
    task.editedby = actor
    task.save()
    if task.task_alloted_to_id != previous_owner and item.owner_id != actor.id:
        _notify(item.owner, task, f'Action item from {item.meeting.number} assigned to you: "{item.description}"')


@transaction.atomic
def finalise(meeting, actor):
    if meeting.is_final:
        raise ValidationError('This meeting is already final.')
    if richtext.is_blank(meeting.minutes):
        raise ValidationError('Write the minutes before finalising the meeting.')
    meeting.status = 'final'
    meeting.finalised_at = timezone.now()
    meeting.finalised_by = actor
    meeting.save(update_fields=['status', 'finalised_at', 'finalised_by', 'updated_at'])
    for item in meeting.action_items.select_related('owner', 'meeting'):
        create_task_for(item, actor)


@transaction.atomic
def mark_done(item, actor):
    if item.status == 'done':
        return
    now = timezone.now()
    item.is_done = True
    item.done_at = now
    item.done_by = actor
    item.save(update_fields=['is_done', 'done_at', 'done_by'])
    task = item.task
    if task and not task.is_closed:
        task.is_closed = True
        task.close_date = now
        task.editedby = actor
        task.save(update_fields=['is_closed', 'close_date', 'editedby', 'edited'])
        if item.owner_id != actor.id:
            _notify(item.owner, task, f'Task "{task.taskname}" has been closed by {actor}.')


@transaction.atomic
def reopen(item, actor):
    item.is_done = False
    item.done_at = None
    item.done_by = None
    item.save(update_fields=['is_done', 'done_at', 'done_by'])
    task = item.task
    if task and task.is_closed:
        task.is_closed = False
        task.close_date = None
        task.request_to_close = False
        task.editedby = actor
        task.save(update_fields=['is_closed', 'close_date', 'request_to_close', 'editedby', 'edited'])
        if item.owner_id != actor.id:
            _notify(item.owner, task, f'Task "{task.taskname}" has been reopened by {actor}.')


def previous_open_items(meeting):
    """Open action items of earlier finalised meetings of the same type: what
    is still outstanding going into this one. Read-only reminder."""
    from .models import ActionItem
    earlier = ActionItem.objects.filter(
        meeting__status='final', meeting__meeting_type=meeting.meeting_type,
        meeting__meeting_date__lte=meeting.meeting_date,
    ).exclude(meeting_id=meeting.pk).select_related('meeting', 'owner', 'task')
    return [item for item in earlier.order_by('due_date', 'id') if item.status == 'open']
