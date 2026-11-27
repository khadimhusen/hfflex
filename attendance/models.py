from django.contrib.auth.models import User
from django.db import models

from employee.models import Worker

from . import shifts


class PunchLog(models.Model):
    """One raw punch: somebody's card or finger on a reader (or a hand-entered one).
    Kept exactly as it came in. The day sheets are worked out from these."""
    SOURCES = [('manual', 'Entered by hand'), ('file', 'Imported file'), ('etimeoffice', 'eTimeOffice')]

    worker = models.ForeignKey(Worker, null=True, blank=True, on_delete=models.PROTECT, related_name='punches')
    # What the reader sent. Kept even when no worker has this code yet, so nothing is lost.
    emp_code = models.CharField(max_length=32)
    punched_at = models.DateTimeField()
    source = models.CharField(max_length=16, choices=SOURCES, default='manual')
    device = models.CharField(max_length=32, blank=True)
    note = models.CharField(max_length=200, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['-punched_at', '-id']
        constraints = [models.UniqueConstraint(fields=['emp_code', 'punched_at'], name='one_punch_per_code_and_time')]
        indexes = [models.Index(fields=['worker', 'punched_at'])]

    def __str__(self):
        return f'{self.emp_code} {self.punched_at:%d/%m/%Y %H:%M}'


class ShiftAssignment(models.Model):
    """The shift one worker works from one date to another (both days included). A worker's
    entries never overlap (services.assign_shift sees to that). A day outside every entry takes
    the shift of the last entry before it; before the first one it is Worker.default_shift."""
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='shift_assignments')
    from_date = models.DateField()
    to_date = models.DateField()
    shift = models.CharField(max_length=10, choices=shifts.CHOICES)
    edited = models.DateTimeField(auto_now=True)
    edited_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['-from_date', 'worker__worker_name']
        constraints = [models.CheckConstraint(check=models.Q(to_date__gte=models.F('from_date')),
                                              name='shift_to_date_not_before_from_date')]
        indexes = [models.Index(fields=['worker', 'from_date'])]

    def __str__(self):
        return f'{self.worker} {self.from_date} to {self.to_date} {self.shift}'


class AttendanceDay(models.Model):
    """One worker, one working day: when they came and left, and what it counts as.
    Rows come from the punches; a row somebody corrected by hand (is_manual) is
    never overwritten by a rebuild."""
    PRESENT, HALF, ABSENT, LEAVE, WEEKLY_OFF, HOLIDAY, REVIEW = (
        'present', 'half', 'absent', 'leave', 'weekly_off', 'holiday', 'review')
    STATUSES = [
        (PRESENT, 'Present'), (HALF, 'Half Day'), (ABSENT, 'Absent'), (LEAVE, 'Paid Leave'),
        (WEEKLY_OFF, 'Weekly Off'), (HOLIDAY, 'Holiday'), (REVIEW, 'Needs Review'),
    ]
    SHIFTS = shifts.CHOICES

    worker = models.ForeignKey(Worker, on_delete=models.PROTECT, related_name='attendance_days')
    date = models.DateField()
    status = models.CharField(max_length=12, choices=STATUSES)
    shift = models.CharField(max_length=10, choices=SHIFTS, blank=True)
    in_time = models.DateTimeField(null=True, blank=True)
    out_time = models.DateTimeField(null=True, blank=True)       # the next day for a night shift
    worked_minutes = models.PositiveIntegerField(default=0)       # first to last punch, less the break
    break_start = models.DateTimeField(null=True, blank=True)       # Break Start: the 2nd punch, when the day has four or more
    break_end = models.DateTimeField(null=True, blank=True)        # Break End: the 3rd
    break_minutes = models.PositiveIntegerField(default=0)
    overtime_minutes = models.PositiveIntegerField(default=0)
    remarks = models.CharField(max_length=200, blank=True)
    is_manual = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    edited = models.DateTimeField(auto_now=True)
    edited_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        ordering = ['-date', 'worker__worker_name']
        constraints = [models.UniqueConstraint(fields=['worker', 'date'], name='one_attendance_row_per_worker_per_day')]
        indexes = [models.Index(fields=['date'])]

    def __str__(self):
        return f'{self.worker} {self.date} {self.get_status_display()}'
