"""Fill the LOCAL database with made-up attendance so the screens can be tried out.

    python manage.py seed_dummy_attendance            # the last 30 days, every active worker
    python manage.py seed_dummy_attendance --days 60
    python manage.py seed_dummy_attendance --clear    # remove all of it again

The punches go in through the same code real punches will (record_punches), so the day
sheets, the "needs review" list and the unknown-code list behave exactly as they will for
real data. Everything made here is tagged (punch device "DEMO", day remarks starting
"Demo:") so --clear removes it and nothing else. Never run this on the live server."""
import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from attendance import rules, services
from attendance.models import AttendanceDay, PunchLog
from employee.models import Worker

DEVICE = 'DEMO'
REMARK = 'Demo:'
DEMO_HOLIDAYS = {date(2026, 11, 8): 'Diwali'}
UNKNOWN_CODES = {'9901': 6, '9902': 3}        # punches from cards nobody has been given a worker for

# Days that are always made for the "Needs Review" screens: in, ONE break punch, out. Each is
# (how many days ago, [(hour, minute, days after the day began)]). They go to different workers.
SAMPLE_NOTE = 'Sample: single break punch'
REVIEW_SAMPLES = [
    (1, [(8, 0, 0), (13, 10, 0), (16, 30, 0)]),     # 08:00, 13:10, 16:30 -- is 13:10 the start or the end?
    (1, [(8, 5, 0), (12, 30, 0), (17, 10, 0)]),     # looks like a Break Start; the Break End is missing
    (1, [(7, 55, 0), (13, 30, 0), (17, 15, 0)]),    # looks like a Break End; the Break Start is missing
    (1, [(20, 0, 0), (0, 45, 1), (5, 0, 1)]),       # a night shift with one break punch after midnight
    (2, [(8, 10, 0), (12, 45, 0), (17, 20, 0)]),
    (2, [(8, 0, 0), (13, 0, 0), (16, 45, 0)]),
]


def tag(text):
    return f'{REMARK} {text}'


class Command(BaseCommand):
    help = 'Add (or with --clear, remove) made-up attendance on the local database.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30, help='how many days back to fill (default 30)')
        parser.add_argument('--seed', type=int, default=2026, help='same number, same made-up data')
        parser.add_argument('--clear', action='store_true', help='remove the demo data instead of adding it')

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Refusing to run: DEBUG is off, so this looks like a live server. '
                               'This command only makes made-up data for a local development database.')
        if options['clear']:
            return self.clear()
        if not 1 <= options['days'] <= 366:
            raise CommandError('--days must be between 1 and 366')
        self.fill(options['days'], random.Random(options['seed']))

    # ---- removing ---------------------------------------------------------------

    def clear(self):
        punches = PunchLog.objects.filter(device=DEVICE)
        touched = defaultdict(list)
        for worker_id, when in punches.exclude(worker__isnull=True).values_list('worker_id', 'punched_at'):
            touched[worker_id].append(when.date())
        deleted_punches = punches.count()
        punches.delete()
        # Days built from those punches go (or are rebuilt from any punches that remain).
        for worker in Worker.objects.filter(pk__in=touched):
            services.rebuild_days(worker, min(touched[worker.pk]) - timedelta(days=1),
                                  max(touched[worker.pk]) + timedelta(days=1))
        deleted_days = AttendanceDay.objects.filter(remarks__startswith=REMARK).delete()[0]
        self.stdout.write(self.style.SUCCESS(
            f'Removed {deleted_punches} demo punches and {deleted_days} demo day rows.'))

    # ---- adding -----------------------------------------------------------------

    def fill(self, days, rng):
        now = datetime.now().replace(microsecond=0)
        today = now.date()
        first_day = today - timedelta(days=days)
        workers = list(Worker.objects.filter(is_active=True).exclude(emp_code__isnull=True).exclude(emp_code='')
                       .order_by('worker_name'))
        if not workers:
            raise CommandError('There are no active workers with an employee code to make attendance for.')

        people = {w.pk: self.personality(rng) for w in workers}
        per_day, manual = {}, []
        for worker in workers:
            who = people[worker.pk]
            for offset in range(days + 1):
                day = first_day + timedelta(days=offset)
                if self.not_employed(worker, day):
                    continue
                if day in DEMO_HOLIDAYS:
                    manual.append((worker, day, AttendanceDay.HOLIDAY, tag(DEMO_HOLIDAYS[day])))
                elif day.weekday() == who['weekly_off']:
                    manual.append((worker, day, AttendanceDay.WEEKLY_OFF, tag('weekly off')))
                elif day < today and rng.random() < who['leave']:
                    manual.append((worker, day, AttendanceDay.LEAVE, tag('paid leave')))
                elif day < today and rng.random() < who['absent']:
                    continue                      # no punches: becomes an Absent row below
                else:
                    per_day[(worker.pk, day)] = self.punches_for(worker, day, who, rng, now)

        samples = self.add_review_samples(per_day, today, workers)
        rows = [punch for punches in per_day.values() for punch in punches]

        # Cards nobody owns yet (they show up in the "unknown codes" list).
        for code, count in UNKNOWN_CODES.items():
            for _ in range(count):
                day = first_day + timedelta(days=rng.randrange(1, days + 1))
                when = datetime.combine(day, time(rng.choice([8, 9, 20]), rng.randrange(60)))
                if when <= now:
                    rows.append({'emp_code': code, 'punched_at': when, 'device': DEVICE, 'note': 'dummy data'})

        for worker, day, status, remarks in manual:
            services.set_day(worker, day, status, None, remarks=remarks)
        result = services.record_punches(rows, source='file')

        absent = 0
        for offset in range(days):                # yesterday and earlier: no punch and nothing else = Absent
            day = first_day + timedelta(days=offset)
            have = set(AttendanceDay.objects.filter(date=day).values_list('worker_id', flat=True))
            for worker in workers:
                if worker.pk in have or self.not_employed(worker, day):
                    continue
                AttendanceDay.objects.create(worker=worker, date=day, status=AttendanceDay.ABSENT,
                                             remarks=tag('no punch'))
                absent += 1

        self.report(result, len(manual), absent, first_day, today)
        self.stdout.write(f'Single-break-punch days made for the Needs Review screens: {samples}.')

    @staticmethod
    def add_review_samples(per_day, today, workers):
        """Give a few workers a day with exactly one break punch (three punches in all), so the
        "Needs Review" screens always have these cases to try. Their normal day is replaced.
        Chosen without touching the main random numbers, so the rest of the data stays the same."""
        rng = random.Random(len(workers))
        used, made = set(), 0
        for ago, pattern in REVIEW_SAMPLES:
            day = today - timedelta(days=ago)
            candidates = sorted(key for key, punches in per_day.items()
                                if key[1] == day and punches and key[0] not in used)
            if not candidates:
                continue
            key = rng.choice(candidates)
            code = per_day[key][0]['emp_code']
            punches = [{'emp_code': code, 'punched_at': datetime.combine(day + timedelta(days=plus), time(h, m)),
                        'device': DEVICE, 'note': SAMPLE_NOTE} for h, m, plus in pattern]
            # Nothing else of this worker may fall within a work session of these punches, or the
            # system would count it as part of the same day (a next-morning shift would add a fourth
            # punch to a night sample): clear the neighbouring days' punches inside that window.
            window_start = punches[0]['punched_at'] - rules.SESSION_SPAN
            window_end = punches[-1]['punched_at'] + rules.SESSION_SPAN
            for neighbour in ((key[0], day - timedelta(days=1)), (key[0], day + timedelta(days=1))):
                if neighbour in per_day:
                    per_day[neighbour] = [p for p in per_day[neighbour]
                                          if not window_start <= p['punched_at'] <= window_end]
            per_day[key] = punches
            used.add(key[0])
            made += 1
        return made

    @staticmethod
    def not_employed(worker, day):
        return day < worker.date_of_join or bool(worker.date_of_releave and day > worker.date_of_releave)

    @staticmethod
    def personality(rng):
        """How one worker behaves: which shift, which weekly off day, how often late or away."""
        return {
            'shift': rng.choices(['day', 'night', 'rotating'], [60, 20, 20])[0],
            'weekly_off': rng.randrange(7),
            'late': rng.uniform(0.02, 0.18),
            'absent': rng.uniform(0.01, 0.07),
            'leave': rng.uniform(0.0, 0.03),
            'zero_padded': rng.random() < 0.1,    # this reader sends the code as 01003, not 1003
        }

    @staticmethod
    def punches_for(worker, day, who, rng, now):
        night = who['shift'] == 'night' or (who['shift'] == 'rotating' and day.isocalendar()[1] % 2 == 0)
        start = time(20, 0) if night else time(8, 0)
        came = datetime.combine(day, start) + timedelta(minutes=int(rng.gauss(0, 7)))
        if rng.random() < who['late']:
            came += timedelta(minutes=rng.randrange(20, 90))
        stay = timedelta(hours=9, minutes=int(rng.gauss(0, 12)))
        roll = rng.random()
        if roll < 0.05:
            stay = timedelta(hours=4, minutes=rng.randrange(20, 60))          # half day
        elif roll < 0.07:
            stay = timedelta(minutes=rng.randrange(30, 120))                  # left almost at once
        elif roll < 0.20:
            stay += timedelta(minutes=rng.randrange(30, 120))                 # overtime
        left = came + stay

        code = worker.emp_code.strip()
        code = '0' + code if who['zero_padded'] else code
        times = [came]
        if rng.random() < 0.03:
            times.append(came + timedelta(seconds=rng.randrange(20, 90)))     # tapped twice
        # Break: starts about four and a half hours in, ends 25-55 minutes later. Most days have both
        # punches; some forget both (no break recorded) and a few forget one (a day for review).
        if stay > timedelta(hours=6):
            break_start = came + timedelta(hours=4, minutes=rng.randrange(15, 50))
            break_end = break_start + timedelta(minutes=rng.randrange(25, 56))
            roll = rng.random()
            if roll < 0.86:
                times += [break_start, break_end]
            elif roll < 0.89:
                times.append(rng.choice([break_start, break_end]))
        if rng.random() >= 0.03:                                              # 3% forget to punch out
            times.append(left)
        return [{'emp_code': code, 'punched_at': t, 'device': DEVICE, 'note': 'dummy data'}
                for t in times if t <= now]                                   # nothing in the future

    def report(self, result, manual, absent, first_day, today):
        self.stdout.write(self.style.SUCCESS(
            f'Punches: {result["created"]} added ({result["duplicates"]} already there, '
            f'{result["unmatched"]} from unknown cards).'))
        self.stdout.write(f'Hand-set days (weekly off, leave, holiday): {manual}.  Absent days: {absent}.')
        counts = defaultdict(int)
        for status in AttendanceDay.objects.filter(date__gte=first_day, date__lte=today).values_list('status', flat=True):
            counts[status] += 1
        self.stdout.write('Day rows by status: ' + ', '.join(f'{k} {v}' for k, v in sorted(counts.items())))
        self.stdout.write(f'Dates filled: {first_day:%d/%m/%Y} to {today:%d/%m/%Y}. Remove with: '
                          f'python manage.py seed_dummy_attendance --clear')
