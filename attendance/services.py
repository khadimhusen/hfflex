"""Attendance logic: raw punches in, one row per worker per day out."""
import calendar
from bisect import bisect_right
from collections import defaultdict
from datetime import date as date_type, datetime, time, timedelta

from django.db import transaction
from django.db.models import Count, Max, Min, Q
from django.utils.dateparse import parse_datetime

from employee.models import Worker

from . import rules, shifts
from .models import AttendanceDay, PunchLog, ShiftAssignment

NO_TIME_STATUSES = (AttendanceDay.ABSENT, AttendanceDay.LEAVE, AttendanceDay.WEEKLY_OFF, AttendanceDay.HOLIDAY)
PUNCH_STATUSES = (AttendanceDay.PRESENT, AttendanceDay.HALF, AttendanceDay.REVIEW)


class AttendanceError(ValueError):
    """Something the person using the screen must fix; the message is shown to them."""


# ---- worker codes ---------------------------------------------------------------

def clean_code(value):
    """A device code as stored: trimmed, and without leading zeros ("0037" and "37" are one person)."""
    text = str(value if value is not None else '').strip()
    return text.lstrip('0') or ('0' if text else '')


class WorkerMatcher:
    """Finds the worker a code belongs to on a given day. Load once, use for a whole batch."""

    def __init__(self):
        self.by_code = defaultdict(list)
        for worker in Worker.objects.exclude(emp_code__isnull=True).exclude(emp_code=''):
            self.by_code[clean_code(worker.emp_code)].append(worker)

    def find(self, code, day):
        """The worker with this code who was employed on `day`. A code shared by two workers
        (one has left) goes to whoever was employed then; if that is still not one person,
        None, so the punch is left for somebody to sort out rather than guessed."""
        candidates = self.by_code.get(clean_code(code), [])
        employed = [w for w in candidates
                    if w.date_of_join <= day and (w.date_of_releave is None or w.date_of_releave >= day)]
        if len(employed) > 1:
            employed = [w for w in employed if w.is_active] or employed
        return employed[0] if len(employed) == 1 else None


# ---- recording punches ----------------------------------------------------------

def _parse_when(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=None, microsecond=0)
    text = str(value or '').strip()
    for fmt in ('%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%d/%m/%Y_%H:%M'):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass
    parsed = parse_datetime(text.replace('T', ' ')) if text else None
    if parsed is None:
        raise ValueError(f'"{text}" is not a date and time')
    return parsed.replace(tzinfo=None, microsecond=0)


def record_punches(rows, source='manual', user=None):
    """Save punches from any source: dicts with emp_code, punched_at (a datetime or text),
    and optionally device and note. Punches already stored are skipped, so the same file
    or the same sync can be run twice safely. Returns the counts and then rebuilds the
    affected days."""
    result = {'received': 0, 'created': 0, 'duplicates': 0, 'invalid': 0, 'unmatched': 0, 'errors': []}
    clean = {}
    for index, row in enumerate(rows, start=1):
        result['received'] += 1
        try:
            code = clean_code(row.get('emp_code'))
            if not code:
                raise ValueError('no employee code')
            when = _parse_when(row.get('punched_at'))
        except (ValueError, AttributeError) as error:
            result['invalid'] += 1
            if len(result['errors']) < 20:
                result['errors'].append(f'Row {index}: {error}')
            continue
        key = (code, when)
        if key in clean:
            result['duplicates'] += 1
            continue
        clean[key] = {'device': str(row.get('device') or '')[:32], 'note': str(row.get('note') or '')[:200]}
    if not clean:
        return result

    first = min(when for _, when in clean)
    last = max(when for _, when in clean)
    codes = {code for code, _ in clean}
    existing = set(PunchLog.objects.filter(punched_at__gte=first, punched_at__lte=last, emp_code__in=codes)
                   .values_list('emp_code', 'punched_at'))
    matcher = WorkerMatcher()
    new_logs, touched = [], defaultdict(list)
    for (code, when), extra in clean.items():
        if (code, when) in existing:
            result['duplicates'] += 1
            continue
        worker = matcher.find(code, when.date())
        if worker is None:
            result['unmatched'] += 1
        else:
            touched[worker.pk].append(when.date())
        new_logs.append(PunchLog(worker=worker, emp_code=code, punched_at=when, source=source,
                                 created_by=user, **extra))
    with transaction.atomic():
        PunchLog.objects.bulk_create(new_logs, batch_size=1000, ignore_conflicts=True)
        for worker_id, days in touched.items():
            rebuild_days(Worker.objects.get(pk=worker_id), min(days), max(days) + timedelta(days=1))
    result['created'] = len(new_logs)
    return result


def relink_punches():
    """After a worker is given (or changes) an employee code: attach the punches that had
    no worker, then rebuild the days they touch."""
    matcher = WorkerMatcher()
    attached, touched = 0, defaultdict(list)
    for punch in PunchLog.objects.filter(worker__isnull=True):
        worker = matcher.find(punch.emp_code, punch.punched_at.date())
        if worker is not None:
            punch.worker = worker
            punch.save(update_fields=['worker'])
            touched[worker.pk].append(punch.punched_at.date())
            attached += 1
    for worker_id, days in touched.items():
        rebuild_days(Worker.objects.get(pk=worker_id), min(days), max(days) + timedelta(days=1))
    return {'attached': attached, 'still_unmatched': PunchLog.objects.filter(worker__isnull=True).count()}


def unmatched_codes():
    """Codes that punched but belong to nobody yet: the list to fix in the worker records."""
    return list(PunchLog.objects.filter(worker__isnull=True).values('emp_code')
                .annotate(punches=Count('id'), first=Min('punched_at'), last=Max('punched_at'))
                .order_by('-punches', 'emp_code'))


# ---- punches -> days ------------------------------------------------------------

def _sessions(times):
    """Punch times (ascending) grouped into work sessions: a session is the punches within
    SESSION_SPAN of its first one. A double tap is one punch."""
    sessions = []
    for when in times:
        if sessions and when - sessions[-1][-1] <= rules.DOUBLE_TAP:
            continue
        if sessions and when - sessions[-1][0] < rules.SESSION_SPAN:
            sessions[-1].append(when)
        else:
            sessions.append([when])
    return sessions


# ---- shifts given for a range of dates ---------------------------------------------
# A worker's ShiftAssignment rows are date ranges (from_date to to_date, both days included) that
# never overlap. The shift on a day is the one of the range the day falls in; a day outside every
# range takes the shift of the last entry before it; before the first entry (or with none at all)
# it is the worker's usual shift, and with that unset the shift is guessed from the punches.

def shift_lookup(worker, date_from, date_to):
    """A function date -> the shift this worker is on that day. (A rebuild reads punches up to two
    days past its range, so entries starting up to then are loaded.)"""
    spans = list(ShiftAssignment.objects.filter(worker=worker, from_date__lte=date_to + timedelta(days=2))
                 .order_by('from_date').values_list('from_date', 'shift'))
    starts = [start for start, _ in spans]
    usual = worker.default_shift

    def shift_on(day):
        i = bisect_right(starts, day) - 1               # the last entry that began on or before the day
        return spans[i][1] if i >= 0 else usual
    return shift_on


def shifts_on(day):
    """Everyone employed on a day with the shift they have then, and why: 'range' (the day is in an
    entry), 'carried' (the last entry before it), 'usual' (their usual shift) or '' (none)."""
    workers = list(Worker.objects.filter(is_active=True, date_of_join__lte=day)
                   .filter(Q(date_of_releave__isnull=True) | Q(date_of_releave__gte=day)).order_by('worker_name'))
    last = {}
    for entry in ShiftAssignment.objects.filter(worker__in=workers, from_date__lte=day).order_by('from_date'):
        last[entry.worker_id] = entry
    rows = []
    for worker in workers:
        entry = last.get(worker.pk)
        if entry:
            source, shift = ('range' if entry.to_date >= day else 'carried'), entry.shift
        else:
            source, shift = ('usual' if worker.default_shift else ''), worker.default_shift
        rows.append({'worker': worker, 'shift': shift, 'source': source, 'entry': entry, 'usual': worker.default_shift})
    return rows


def _rebuild_since(worker, start):
    """Work a worker's days out again from a date to today (the days after an entry took the shift of
    the last one before them, so a change reaches forward). A day earlier, for a 3rd-shift punch the
    evening before. Nothing is read past today: there are no punches yet."""
    today = date_type.today()
    return rebuild_days(worker, start - timedelta(days=1), max(today, start)) if start <= today else 0


def _kept(old, from_date, to_date):
    """What is left of an entry when a new one is given over from_date..to_date: the part before it
    and the part after it (none, one or two date ranges)."""
    one_day = timedelta(days=1)
    parts = []
    if old.from_date < from_date:
        parts.append((old.from_date, from_date - one_day))
    if old.to_date > to_date:
        parts.append((to_date + one_day, old.to_date))
    return parts


def _overlapping(worker, from_date, to_date):
    return ShiftAssignment.objects.filter(worker=worker, from_date__lte=to_date, to_date__gte=from_date)


def shift_conflicts(workers, from_date, to_date):
    """The entries that giving these workers a shift over from_date..to_date would replace or cut
    back, and what would be left of each -- so a person can be asked before it happens."""
    if to_date < from_date:
        raise AttendanceError('The to date must not be before the from date.')
    found = []
    for worker in workers:
        for old in _overlapping(worker, from_date, to_date).select_related('worker').order_by('from_date'):
            found.append({'entry': old, 'kept': _kept(old, from_date, to_date)})
    found.sort(key=lambda c: (c['entry'].worker.worker_name.lower(), c['entry'].from_date))
    return found


@transaction.atomic
def assign_shift(workers, from_date, to_date, shift, user=None):
    """Give workers a shift from one date to another, both included. Entries it overlaps are cut
    back, split or removed so the new one stands (shift_conflicts says which). Days corrected by
    hand are left alone. Returns how many day rows changed."""
    if shift not in shifts.BY_KEY:
        raise AttendanceError('Choose one of the shifts.')
    if to_date < from_date:
        raise AttendanceError('The to date must not be before the from date.')
    changed = 0
    for worker in workers:
        earliest = from_date
        for old in list(_overlapping(worker, from_date, to_date)):
            earliest = min(earliest, old.from_date)
            parts = _kept(old, from_date, to_date)
            if not parts:
                old.delete()
                continue
            if len(parts) == 2:                           # the new entry sits inside it: keep both ends
                ShiftAssignment.objects.create(worker=worker, from_date=parts[1][0], to_date=parts[1][1],
                                               shift=old.shift, edited_by=old.edited_by)
            old.from_date, old.to_date = parts[0]
            old.save()
        ShiftAssignment.objects.create(worker=worker, from_date=from_date, to_date=to_date, shift=shift, edited_by=user)
        changed += _rebuild_since(worker, earliest)
    return changed


@transaction.atomic
def remove_assignment(entry):
    """Take an entry away; its days fall back to the entry before them. Returns how many day rows changed."""
    worker, start = entry.worker, entry.from_date
    entry.delete()
    return _rebuild_since(worker, start)


def session_day(first, shift_on):
    """The working day a session belongs to: the day it started, except that someone on the 3rd
    shift (0:00 to 8:00) who punches in shortly before midnight is working the day that follows."""
    if first.hour >= 20:
        tomorrow = first.date() + timedelta(days=1)
        third = shifts.BY_KEY.get(shift_on(tomorrow))
        if third and third.start_hour == 0:
            return tomorrow
    return first.date()


def shift_for(started):
    """A guess for a worker with no default shift: Day or Night, from when they came in."""
    return 'Day' if rules.DAY_SHIFT_FROM_HOUR <= started.hour < rules.DAY_SHIFT_UNTIL_HOUR else 'Night'


def standard_minutes(shift):
    """Time beyond this counts as overtime: the shift's own length, or the plain
    standard day when the shift is only a guess (shift is '' then)."""
    return shifts.scheduled_minutes(shift) or rules.STANDARD_DAY_MINUTES


def summarise(session, shift=''):
    """One session of punch times -> the fields of the day row.
    shift is the worker's own shift, when they have one; without it the shift is guessed."""
    first, last = session[0], session[-1]
    gross = int((last - first).total_seconds() // 60)
    fields = {'shift': shift or shift_for(first), 'in_time': first, 'out_time': last if len(session) > 1 else None,
              'worked_minutes': gross, 'overtime_minutes': 0, 'remarks': '',
              'break_start': None, 'break_end': None, 'break_minutes': 0}
    pause = 0
    if len(session) >= 4:                      # in, break start, break end, ... out
        fields['break_start'], fields['break_end'] = session[1], session[2]
        pause = int((session[2] - session[1]).total_seconds() // 60)
        fields['break_minutes'] = pause
    worked = max(0, gross - pause) if rules.DEDUCT_BREAK else gross
    fields['worked_minutes'] = worked
    if len(session) == 1:
        fields.update(status=AttendanceDay.REVIEW, worked_minutes=0, remarks='Only one punch: no out time')
    elif len(session) == 3:
        fields.update(status=AttendanceDay.REVIEW, remarks='Three punches: a break punch is missing')
    elif pause > rules.LONG_BREAK_MINUTES:
        fields.update(status=AttendanceDay.REVIEW, remarks=f'Break of {pause // 60}:{pause % 60:02d}: check the punches')
    elif worked >= rules.FULL_DAY_MINUTES:
        fields.update(status=AttendanceDay.PRESENT, overtime_minutes=max(0, worked - standard_minutes(shift)))
    elif worked >= rules.HALF_DAY_MINUTES:
        fields['status'] = AttendanceDay.HALF
    else:
        fields.update(status=AttendanceDay.REVIEW, remarks='Very short stay')
    return fields


def rebuild_days(worker, date_from, date_to):
    """Recalculate a worker's day rows between two dates from their punches.
    Rows corrected by hand are left alone; a row built from punches that no longer exist is removed."""
    window_start = datetime.combine(date_from - timedelta(days=1), time.min)
    window_end = datetime.combine(date_to + timedelta(days=2), time.min)
    times = list(PunchLog.objects.filter(worker=worker, punched_at__gte=window_start, punched_at__lt=window_end)
                 .order_by('punched_at').values_list('punched_at', flat=True))
    shift_on = shift_lookup(worker, date_from, date_to)
    by_date = defaultdict(list)
    for session in _sessions(times):
        day = session_day(session[0], shift_on)
        if date_from <= day <= date_to:
            by_date[day].extend(session)
    existing = {row.date: row for row in AttendanceDay.objects.filter(worker=worker, date__gte=date_from,
                                                                         date__lte=date_to)}
    changed = 0
    for day, punches in by_date.items():
        row = existing.get(day)
        if row is not None and row.is_manual:
            continue
        fields = summarise(sorted(punches), shift_on(day))
        if row is None:
            AttendanceDay.objects.create(worker=worker, date=day, **fields)
        else:
            for name, value in fields.items():
                setattr(row, name, value)
            row.save()
        changed += 1
    for day, row in existing.items():
        if day not in by_date and not row.is_manual and row.status in PUNCH_STATUSES:
            row.delete()                    # its punches are gone
            changed += 1
    return changed


def rebuild_range(date_from, date_to, worker=None):
    workers = [worker] if worker else Worker.objects.filter(
        Q(punches__punched_at__gte=datetime.combine(date_from - timedelta(days=1), time.min),
          punches__punched_at__lt=datetime.combine(date_to + timedelta(days=2), time.min))
        | Q(attendance_days__date__gte=date_from, attendance_days__date__lte=date_to)).distinct()
    return sum(rebuild_days(w, date_from, date_to) for w in workers)


# ---- corrections by hand --------------------------------------------------------

@transaction.atomic
def set_day(worker, day, status, user, in_time=None, out_time=None, shift='', remarks=''):
    """A person's decision for one worker's day. It stays until they clear it."""
    if status not in dict(AttendanceDay.STATUSES):
        raise AttendanceError('Choose a status for the day.')
    if status in NO_TIME_STATUSES:
        in_time = out_time = None
    if in_time and out_time and out_time <= in_time:
        raise AttendanceError('The out time must be after the in time.')
    worked = int((out_time - in_time).total_seconds() // 60) if in_time and out_time else 0
    shift = shift or shift_lookup(worker, day, day)(day)       # the day's own choice, else the worker's shift that week
    overtime = max(0, worked - standard_minutes(shift)) if status == AttendanceDay.PRESENT else 0
    if not shift and in_time:
        shift = shift_for(in_time)
    row, _ = AttendanceDay.objects.update_or_create(worker=worker, date=day, defaults={
        'status': status, 'in_time': in_time, 'out_time': out_time, 'shift': shift if status not in NO_TIME_STATUSES else '',
        'break_start': None, 'break_end': None, 'break_minutes': 0,           # a hand-made day has no break of its own
        'worked_minutes': worked, 'overtime_minutes': overtime, 'remarks': remarks.strip(),
        'is_manual': True, 'edited_by': user})
    return row


@transaction.atomic
def clear_manual(row):
    """Drop a hand-set day and let the punches decide again (nothing is left if there are none)."""
    worker, day = row.worker, row.date
    row.delete()
    rebuild_days(worker, day, day)
    return AttendanceDay.objects.filter(worker=worker, date=day).first()


# ---- who should be here ---------------------------------------------------------

def workers_for(day):
    """Workers on the roster for a day: employed that day, and active (or already with a row)."""
    return Worker.objects.filter(
        Q(is_active=True, date_of_join__lte=day) & (Q(date_of_releave__isnull=True) | Q(date_of_releave__gte=day))
        | Q(attendance_days__date=day)).distinct().order_by('worker_name')


def roster(day):
    rows = {r.worker_id: r for r in AttendanceDay.objects.filter(date=day).select_related('worker')}
    return [(worker, rows.get(worker.pk)) for worker in workers_for(day)]


def holiday_on(day):
    """The company holiday on this date (from the holiday list), or None."""
    try:
        from holidaylist.models import Holiday
    except ImportError:             # the holiday list is not installed
        return None
    return Holiday.objects.filter(date=day).first()


@transaction.atomic
def mark_absent(day, user=None):
    """End-of-day: everyone on the roster with no row yet is Absent -- or on Holiday, when the
    date is on the holiday list. A punch that arrives later replaces this (it is not a
    hand-made decision)."""
    holiday = holiday_on(day)
    status, remarks = (AttendanceDay.HOLIDAY, f'Holiday: {holiday.name}') if holiday else (AttendanceDay.ABSENT, 'No punch')
    created = 0
    for worker, row in roster(day):
        if row is None:
            AttendanceDay.objects.create(worker=worker, date=day, status=status, remarks=remarks, edited_by=user)
            created += 1
    return created


# ---- the month sheet ------------------------------------------------------------

def month_range(year, month):
    return date_type(year, month, 1), date_type(year, month, calendar.monthrange(year, month)[1])


def punches_by_session_day(worker, date_from, date_to):
    """Every raw punch of a worker (double taps included), filed under the day its work session
    started -- so a night shift's morning out-punch sits with the evening it belongs to."""
    window_start = datetime.combine(date_from - timedelta(days=1), time.min)
    window_end = datetime.combine(date_to + timedelta(days=2), time.min)
    punches = list(PunchLog.objects.filter(worker=worker, punched_at__gte=window_start, punched_at__lt=window_end)
                   .order_by('punched_at', 'id'))
    starts = [session[0] for session in _sessions([p.punched_at for p in punches])]
    shift_on = shift_lookup(worker, date_from, date_to)
    by_day, current = defaultdict(list), -1
    for punch in punches:
        while current + 1 < len(starts) and starts[current + 1] <= punch.punched_at:
            current += 1
        day = session_day(starts[current], shift_on) if current >= 0 else None
        if day and date_from <= day <= date_to:
            by_day[day].append(punch)
    return by_day


def person_month(worker, year, month):
    """One worker's month, every calendar day in order: the day row (or none), whether they were
    employed that day, and the company holiday on it. Plus the same totals the month sheet shows."""
    first, last = month_range(year, month)
    rows = {r.date: r for r in AttendanceDay.objects.filter(worker=worker, date__gte=first, date__lte=last)
            .select_related('worker', 'edited_by')}
    holidays = {}
    try:
        from holidaylist.models import Holiday
        holidays = {h.date: h.name for h in Holiday.objects.filter(date__gte=first, date__lte=last)}
    except ImportError:             # the holiday list is not installed
        pass
    punches_by_day = punches_by_session_day(worker, first, last)
    days, counts, worked, overtime = [], defaultdict(int), 0, 0
    for number in range(1, last.day + 1):
        day = date_type(year, month, number)
        row = rows.get(day)
        employed = day >= worker.date_of_join and (worker.date_of_releave is None or day <= worker.date_of_releave)
        days.append({'date': day, 'employed': employed, 'holiday': holidays.get(day, ''), 'row': row,
                     'punches': punches_by_day.get(day, [])})
        if row is not None:
            counts[row.status] += 1
            worked += row.worked_minutes
            overtime += row.overtime_minutes
    counts = dict(counts)
    paid = (counts.get(AttendanceDay.PRESENT, 0) + counts.get(AttendanceDay.LEAVE, 0)
            + counts.get(AttendanceDay.WEEKLY_OFF, 0) + counts.get(AttendanceDay.HOLIDAY, 0)
            + counts.get(AttendanceDay.HALF, 0) / 2)
    return {'days': days, 'counts': counts, 'worked_minutes': worked, 'overtime_minutes': overtime,
            'paid_days': paid, 'not_marked': sum(1 for d in days if d['employed'] and d['row'] is None
                                                  and d['date'] <= date_type.today())}


def month_sheet(year, month):
    """Every worker with a row that month (or on the roster), a status per day, and totals."""
    first, last = month_range(year, month)
    rows = defaultdict(dict)
    for row in AttendanceDay.objects.filter(date__gte=first, date__lte=last).select_related('worker'):
        rows[row.worker_id][row.date.day] = row
    workers = {w.pk: w for w in Worker.objects.filter(pk__in=rows)}
    for worker in Worker.objects.filter(is_active=True, date_of_join__lte=last).filter(
            Q(date_of_releave__isnull=True) | Q(date_of_releave__gte=first)):
        workers.setdefault(worker.pk, worker)
    sheet = []
    for worker in sorted(workers.values(), key=lambda w: (w.worker_name or '').lower()):
        days = rows.get(worker.pk, {})
        counts = defaultdict(int)
        worked = overtime = 0
        for row in days.values():
            counts[row.status] += 1
            worked += row.worked_minutes
            overtime += row.overtime_minutes
        sheet.append({'worker': worker, 'days': days, 'counts': dict(counts), 'worked_minutes': worked,
                      'overtime_minutes': overtime,
                      'paid_days': counts[AttendanceDay.PRESENT] + counts[AttendanceDay.LEAVE]
                      + counts[AttendanceDay.WEEKLY_OFF] + counts[AttendanceDay.HOLIDAY]
                      + counts[AttendanceDay.HALF] / 2})
    return sheet
