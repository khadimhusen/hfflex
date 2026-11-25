"""Giving a task a new target date, and asking for one -- the rules, shared by the old pages
(task/views.py) and the API (task/api_review.py) so both behave the same.

Each function answers with an Outcome instead of talking to the browser: `ok`, a `level` for
the message ('success' / 'error' / 'info'), the `text`, and a `code` saying what happened."""
from collections import namedtuple
from datetime import date as date_type, datetime, timedelta

from django.utils.dateparse import parse_date, parse_datetime

from . import lock
from .models import Notification, TaskMsg

ASK_TEXT = 'Please change the target date of this task.'

Outcome = namedtuple('Outcome', 'ok level text code')


def person(user):
    return (user.get_full_name().strip() or user.username) if user else ''


def parse_target(text, current):
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


def asked_recently(user, task, now=None):
    """Has this user already asked about this task within the last hour?"""
    return TaskMsg.objects.filter(task=task, createdby=user, msg_text__startswith=ASK_TEXT,
                                  created__gte=(now or datetime.now()) - timedelta(hours=1)).exists()


def change_date(task, user, raw_date):
    """The person who created (allotted) a task gives it a new target date, whoever it is
    assigned to: it also frees the assignee if the task had locked them. It is noted in the task
    chat and the assignee is told (unless the creator gave the task to themselves)."""
    if user != task.createdby:
        return Outcome(False, 'error', 'Only the person who allotted this task can change its target date.', 'forbidden')
    if task.is_closed:
        return Outcome(False, 'error', 'This task is closed.', 'closed')
    new = parse_target(raw_date, task.target_date)
    if new is None:
        return Outcome(False, 'error', 'Give a valid target date.', 'invalid')
    if new.date() < date_type.today():
        return Outcome(False, 'error', 'The new target date cannot be in the past.', 'past')
    old = task.target_date
    task.target_date = new
    task.editedby = user
    task.save()
    TaskMsg.objects.create(task=task, createdby=user,
                           msg_text=f'Target date changed from {old:%d/%m/%Y %H:%M} to {new:%d/%m/%Y %H:%M} by {person(user)}.')
    if task.task_alloted_to_id != user.pk:
        Notification.objects.create(
            user=task.task_alloted_to, task=task,
            message=f'{person(user)} changed the target date of "{task.taskname}" to {new:%d/%m/%Y}.')
    return Outcome(True, 'success', f'Target date changed to {new:%d/%m/%Y %H:%M}.', 'ok')


def ask_for_date(task, user):
    """The assignee of an overdue task asks whoever allotted it for a new target date: a message
    in the task chat plus a notification. Once an hour per task is plenty."""
    creator = task.createdby
    if creator is None or creator == user:
        return Outcome(False, 'error', 'There is nobody else to ask: you allotted this task yourself.', 'nobody')
    if asked_recently(user, task):
        return Outcome(False, 'info', f'You already asked {person(creator)}. Please wait for the new date.', 'recent')
    days = max(lock.days_overdue(task), 0)
    TaskMsg.objects.create(task=task, createdby=user,
                           msg_text=f'{ASK_TEXT} It is {days} day(s) overdue and I cannot continue until it changes.')
    Notification.objects.create(
        user=creator, task=task,
        message=f'{person(user)} asks you to change the target date of "{task.taskname}" ({days} day(s) overdue).')
    return Outcome(True, 'success', f'{person(creator)} has been asked to change the target date.', 'ok')
