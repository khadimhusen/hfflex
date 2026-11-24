"""The "go through every due task" review shown right after login.

At login a pop-up lists the user's pending tasks. Tasks due today or earlier have to be
gone through: each is either done, or put off with "Later" -- from the pop-up itself, or
from the task's own page after "Open". Which ones were put off is remembered in the
session (`task_review`), so the review survives moving between pages. While a due task
is still not put off, the job list shows the pop-up again. When the last one is put off
(or closed) the review is over.

Nothing here touches the database except reading Task."""
from datetime import date as date_type, datetime, time

from . import lock
from .models import Task

UPCOMING_SHOWN = 10          # tasks not due yet that are listed for information
REVIEW_KEY = 'task_review'   # session: {'day': 'YYYY-MM-DD', 'postponed': [task ids]}


def _today(today=None):
    return today or date_type.today()


def end_of(day):
    return datetime.combine(day, time.max)


def is_due(task, today=None):
    """Due today or earlier (the time of day does not matter)."""
    return task.target_date <= end_of(_today(today))


def _open_tasks(user):
    return (Task.objects.filter(task_alloted_to=user, is_closed=False)
            .select_related('createdby').order_by('target_date', 'id'))


# ---- the review in the session ------------------------------------------------------

def _review(session, today=None):
    """The review in progress, or None. A review belongs to the day it started: the next
    day it is over, so tasks that become due overnight do not trap a long-lived session."""
    review = session.get(REVIEW_KEY)
    if not review:
        return None
    if review.get('day') != _today(today).isoformat():
        session.pop(REVIEW_KEY, None)
        return None
    return review


def start_review(session, today=None):
    session[REVIEW_KEY] = {'day': _today(today).isoformat(), 'postponed': []}


def postponed_ids(session, today=None):
    review = _review(session, today)
    return set(review['postponed']) if review else set()


def due_remaining(user, session, today=None):
    """Due tasks still to be gone through: due, open, and not put off yet."""
    if _review(session, today) is None:
        return []
    skipped = postponed_ids(session, today)
    return [t for t in _open_tasks(user).filter(target_date__lte=end_of(_today(today))) if t.id not in skipped]


def review_in_progress(user, session, today=None):
    """True while a due task is left; the review ends itself when none is."""
    if _review(session, today) is None:
        return False
    if due_remaining(user, session, today):
        return True
    session.pop(REVIEW_KEY, None)
    return False


def can_postpone(user, session, task, today=None):
    """Should this task's own page offer a Later button?"""
    return (task.task_alloted_to_id == user.pk and not task.is_closed and is_due(task, today)
            and not lock.is_locking(task, today)                   # too late for Later: the date must change
            and not lock.locked_tasks(user, today).exists()        # nor for anything else while the user is locked
            and _review(session, today) is not None and task.id not in postponed_ids(session, today))


def postpone(user, session, task, today=None):
    """Put a due task off. Returns how many due tasks are still left (0 ends the review)."""
    review = _review(session, today)
    if (review is None or not is_due(task, today) or lock.is_locking(task, today)
            or lock.locked_tasks(user, today).exists()):          # a locked user puts nothing off
        return len(due_remaining(user, session, today))
    if task.id not in review['postponed']:
        review['postponed'].append(task.id)
        session.modified = True
    remaining = len(due_remaining(user, session, today))
    if remaining == 0:
        session.pop(REVIEW_KEY, None)
    return remaining


# ---- what the pop-up lists ----------------------------------------------------------

def login_popup_tasks(user, today=None, session=None):
    """Every open task of the user that is due today or earlier (all of them, so none of the
    overdue ones can slip past), then the next few that are not due yet. With a session, due
    tasks already put off in this review are left out."""
    skipped = postponed_ids(session, today) if session is not None else set()
    tasks = _open_tasks(user)
    day_end = end_of(_today(today))
    due = [t for t in tasks.filter(target_date__lte=day_end) if t.id not in skipped]
    listed = due + list(tasks.filter(target_date__gt=day_end)[:UPCOMING_SHOWN])
    for task in listed:
        task.locks = lock.is_locking(task, today)      # past its limit: no Later, the date must change
    return listed


def popup_for_request(request, today=None):
    """The tasks for the job list's pop-up, or [] when it should not show: right after login,
    and again on every visit while a due task has not been put off."""
    user, session = request.user, request.session
    show = session.pop('show_pending_tasks', False)
    in_progress = review_in_progress(user, session, today)
    if not (show or in_progress):
        return []
    if in_progress:
        return login_popup_tasks(user, today, session)
    tasks = login_popup_tasks(user, today)                 # a fresh login: the review starts here
    if any(is_due(t, today) for t in tasks):
        start_review(session, today)
    return tasks
