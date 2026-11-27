"""The shifts the factory runs. Plain data, no models, so any app can import it.

A shift has a name, a start time and a length. The length is what overtime is measured
against: time worked beyond it counts as overtime."""
from collections import namedtuple

Shift = namedtuple('Shift', 'key label start_hour start_minute minutes')

SHIFTS = [
    Shift('Day', 'Day', 8, 0, 12 * 60),
    Shift('Night', 'Night', 20, 0, 12 * 60),
    Shift('1st', '1st', 8, 0, 8 * 60),
    Shift('2nd', '2nd', 16, 0, 8 * 60),
    Shift('3rd', '3rd', 0, 0, 8 * 60),
    Shift('General', 'General', 9, 0, 9 * 60),
]
BY_KEY = {shift.key: shift for shift in SHIFTS}


def times_text(shift):
    """'08:00-20:00' (the end past midnight is just a clock time: 16:00-00:00)."""
    end = (shift.start_hour * 60 + shift.start_minute + shift.minutes) % (24 * 60)
    return f'{shift.start_hour:02d}:{shift.start_minute:02d}–{end // 60:02d}:{end % 60:02d}'


# For model fields: the stored value, and what a person reads in a dropdown.
CHOICES = [(shift.key, f'{shift.label} ({times_text(shift)})') for shift in SHIFTS]


def scheduled_minutes(key):
    """How long the shift is, or None when the name is not one of ours."""
    shift = BY_KEY.get(key)
    return shift.minutes if shift else None
