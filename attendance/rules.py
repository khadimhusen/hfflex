"""How punches become a day of attendance. Everything a factory might want to
tune is here, in one place."""
from datetime import timedelta

# Minutes between the first and last punch of a work session.
FULL_DAY_MINUTES = 7 * 60          # at least this long: Present
HALF_DAY_MINUTES = 4 * 60          # at least this long (but under a full day): Half Day
STANDARD_DAY_MINUTES = 8 * 60      # time beyond this on a Present day counts as overtime

# Break: when a day has four or more punches, the 2nd and 3rd are the break (Break Start, Break End).
DEDUCT_BREAK = True                # True: the break comes off the worked time; False: it is only recorded
LONG_BREAK_MINUTES = 2 * 60        # a longer break than this is probably not a normal one: the day is sent for review

# A work session is every punch within this long of its first one. So a night shift (in at
# 20:00, out at 08:00 the next morning) stays one session, and back-to-back 12-hour shifts
# (out at 08:00, in again at 20:00) are two. Longer than any real shift, shorter than a day.
SESSION_SPAN = timedelta(hours=16)

# A session that starts before this hour of the day is a Day shift, otherwise a Night shift.
DAY_SHIFT_FROM_HOUR = 4
DAY_SHIFT_UNTIL_HOUR = 16

# Punches this close to the previous one (a double tap on the reader) are the same punch.
DOUBLE_TAP = timedelta(minutes=2)
