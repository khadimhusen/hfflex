import datetime
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from attendance import services
from attendance.models import AttendanceDay, PunchLog
from employee.models import Worker


def run(*args):
    out = StringIO()
    call_command('seed_dummy_attendance', *args, stdout=out)
    return out.getvalue()


@override_settings(DEBUG=True)
class SeedDummyAttendanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.worker = Worker.objects.create(worker_name='SEEDTEST WORKER', emp_code='7771',
                                           date_of_join=datetime.date(2001, 1, 1))
        cls.leaver = Worker.objects.create(worker_name='SEEDTEST LEAVER', emp_code='7772',
                                           date_of_join=datetime.date(2001, 1, 1),
                                           date_of_releave=datetime.date(2001, 1, 2))

    def setUp(self):
        run('--clear')                  # start from nothing, whatever demo data is already in the database

    def mine(self):
        return AttendanceDay.objects.filter(worker=self.worker)

    def test_it_makes_punches_and_day_rows_for_active_workers(self):
        run('--days', '14')
        self.assertTrue(PunchLog.objects.filter(worker=self.worker, device='DEMO').exists())
        self.assertGreaterEqual(self.mine().count(), 14)             # one row for every day of the span
        statuses = set(self.mine().values_list('status', flat=True))
        self.assertIn(AttendanceDay.PRESENT, statuses)

    def test_it_makes_unknown_card_punches_for_the_unknown_codes_list(self):
        run('--days', '30')
        codes = {row['emp_code'] for row in services.unmatched_codes()}
        self.assertTrue({'9901', '9902'} <= codes)

    def test_a_worker_who_has_left_gets_nothing_after_leaving(self):
        run('--days', '30')
        self.assertFalse(AttendanceDay.objects.filter(worker=self.leaver).exists())   # left in 2001

    def test_running_it_twice_adds_no_duplicate_punches(self):
        run('--days', '10')
        first = PunchLog.objects.filter(device='DEMO').count()
        run('--days', '10')
        self.assertEqual(PunchLog.objects.filter(device='DEMO').count(), first)

    def test_clear_removes_only_the_demo_data(self):
        today = datetime.date.today()
        keep_day = today - datetime.timedelta(days=3)
        services.set_day(self.worker, keep_day, AttendanceDay.PRESENT, None, remarks='a real decision')
        real = PunchLog.objects.create(worker=self.worker, emp_code='7771', source='manual',
                                       punched_at=datetime.datetime.combine(today - datetime.timedelta(days=40),
                                                                            datetime.time(8, 0)))
        run('--days', '14')
        self.assertTrue(PunchLog.objects.filter(device='DEMO').exists())
        run('--clear')
        self.assertFalse(PunchLog.objects.filter(device='DEMO').exists())
        self.assertFalse(AttendanceDay.objects.filter(remarks__startswith='Demo:').exists())
        self.assertTrue(PunchLog.objects.filter(pk=real.pk).exists())
        # a hand-made day that was never the demo's is still there, unchanged
        row = AttendanceDay.objects.get(worker=self.worker, date=keep_day)
        self.assertEqual((row.status, row.remarks), (AttendanceDay.PRESENT, 'a real decision'))
        self.assertTrue(row.is_manual)

    def test_the_same_seed_gives_the_same_data(self):
        run('--days', '10', '--seed', '5')
        first = sorted(PunchLog.objects.filter(device='DEMO', worker=self.worker).values_list('punched_at', flat=True))
        run('--clear')
        run('--days', '10', '--seed', '5')
        second = sorted(PunchLog.objects.filter(device='DEMO', worker=self.worker).values_list('punched_at', flat=True))
        self.assertEqual(first, second)

    def test_bad_days_are_refused(self):
        with self.assertRaises(CommandError):
            run('--days', '0')


@override_settings(DEBUG=True)
class ReviewSampleTests(TestCase):
    """The seeded data always has days with one break punch, for the Needs Review screens."""

    @classmethod
    def setUpTestData(cls):
        for number in range(12):
            Worker.objects.create(worker_name=f'SAMPLE WORKER {number:02d}', emp_code=f'77{number:02d}',
                                  date_of_join=datetime.date(2001, 1, 1))

    def setUp(self):
        run('--clear')
        run('--days', '10')

    def sample_days(self):
        punches = PunchLog.objects.filter(note='Sample: single break punch').order_by('worker_id', 'punched_at')
        by_worker = {}
        for punch in punches:
            by_worker.setdefault(punch.worker_id, []).append(punch.punched_at)
        return by_worker

    def test_there_are_sample_days_with_exactly_three_punches_and_they_need_review(self):
        samples = self.sample_days()
        self.assertGreaterEqual(len(samples), 4)
        for worker_id, times in samples.items():
            self.assertEqual(len(times), 3)
            row = AttendanceDay.objects.get(worker_id=worker_id, date=times[0].date())
            self.assertEqual(row.status, AttendanceDay.REVIEW)
            self.assertIn('break punch is missing', row.remarks)
            self.assertIsNone(row.break_start)

    def test_the_example_of_08_00_13_10_16_30_is_among_them(self):
        shapes = {tuple(t.strftime('%H:%M') for t in times) for times in self.sample_days().values()}
        self.assertIn(('08:00', '13:10', '16:30'), shapes)

    def test_a_night_shift_sample_is_not_spoiled_by_the_next_morning(self):
        night = [times for times in self.sample_days().values() if times[0].hour == 20]
        self.assertTrue(night)
        for times in night:
            self.assertEqual([t.strftime('%H:%M') for t in times], ['20:00', '00:45', '05:00'])
            row = AttendanceDay.objects.get(worker=PunchLog.objects.get(punched_at=times[0]).worker, date=times[0].date())
            self.assertEqual(row.status, AttendanceDay.REVIEW)
            self.assertIn('Three punches', row.remarks)       # not a "break of 4:15" made from a fourth punch

    def test_clear_removes_the_samples_too(self):
        run('--clear')
        self.assertFalse(PunchLog.objects.filter(note='Sample: single break punch').exists())


class RefusesOnALiveServer(TestCase):
    @override_settings(DEBUG=False)
    def test_it_will_not_run_with_debug_off(self):
        with self.assertRaises(CommandError):
            run()
        with self.assertRaises(CommandError):
            run('--clear')
