"""What a holiday does to attendance.

A holiday gives every worker who was employed that day a "Holiday" day row, so the
daily screen, the month sheet and the Excel all show it without anyone marking it.

  * A worker who already has a row is left alone: a hand-made decision (weekly off,
    leave...) always wins, and so does a day they really worked (punches).
  * The "Absent" rows the system makes by itself ("No punch") become Holiday.
  * If somebody does punch in on a holiday, the punches turn that row into Present as
    usual (attendance rebuilds the day from the punches).
  * Deleting a holiday, or moving it to another date, takes the automatic rows back.

Attendance is optional: with that app missing, the holiday list still works on its own."""
from datetime import date as date_type


def _attendance():
    try:
        from attendance import services
        from attendance.models import AttendanceDay
    except ImportError:             # the attendance app is not installed
        return None, None
    return services, AttendanceDay


def holiday_on(day):
    from .models import Holiday
    return Holiday.objects.filter(date=day).first()


def remark_for(holiday):
    return f'Holiday: {holiday.name}'


def apply_to_attendance(holiday):
    """Give the day its Holiday rows. Returns how many rows were made or changed."""
    services, AttendanceDay = _attendance()
    if services is None:
        return 0
    day = holiday.date
    remark = remark_for(holiday)
    existing = {row.worker_id: row for row in AttendanceDay.objects.filter(date=day)}
    changed = 0
    for worker in services.workers_for(day):
        row = existing.get(worker.pk)
        if row is None:
            AttendanceDay.objects.create(worker=worker, date=day, status=AttendanceDay.HOLIDAY, remarks=remark)
            changed += 1
        elif not row.is_manual and row.status == AttendanceDay.ABSENT:
            row.status, row.remarks = AttendanceDay.HOLIDAY, remark
            row.save()
            changed += 1
    # A renamed holiday: refresh the text on the rows the system made.
    for row in AttendanceDay.objects.filter(date=day, status=AttendanceDay.HOLIDAY, is_manual=False) \
            .exclude(remarks=remark):
        row.remarks = remark
        row.save()
        changed += 1
    return changed


def remove_from_attendance(day):
    """The day is no longer a holiday: take back the rows the system made for it. For a day
    already gone the workers with no punch are Absent again (what "mark remaining absent"
    would have made); for a day to come the rows simply go."""
    services, AttendanceDay = _attendance()
    if services is None:
        return 0
    rows = AttendanceDay.objects.filter(date=day, status=AttendanceDay.HOLIDAY, is_manual=False)
    if day < date_type.today():
        return rows.update(status=AttendanceDay.ABSENT, remarks='No punch')
    return rows.delete()[0]
