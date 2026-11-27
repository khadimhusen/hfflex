"""The break: Break Start and Break End are the 2nd and 3rd punch of a day with four or more."""
import datetime
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from attendance import rules, services
from attendance.models import AttendanceDay
from employee.models import Worker

DAYS = '/api/attendance/days/'
D = datetime.date(2001, 3, 5)


def at(day, hour, minute=0):
    return datetime.datetime.combine(day, datetime.time(hour, minute))


class BreakBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('lnstaff', 'a@example.com', 'x', is_staff=True)
        cls.worker = Worker.objects.create(worker_name='LN WORKER', emp_code='5501',
                                           date_of_join=datetime.date(2000, 1, 1))

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.staff)

    def punch(self, *times, day=D):
        services.record_punches([{'emp_code': '5501', 'punched_at': at(day, *t) if isinstance(t, tuple) else t}
                                 for t in times])
        return AttendanceDay.objects.get(worker=self.worker, date=day)


class BreakFromThePunchesTests(BreakBase):
    def test_four_punches_make_a_break_break_that_comes_off_the_hours(self):
        row = self.punch((8, 0), (12, 30), (13, 15), (17, 30))
        self.assertEqual((row.break_start, row.break_end, row.break_minutes), (at(D, 12, 30), at(D, 13, 15), 45))
        self.assertEqual(row.worked_minutes, 9 * 60 + 30 - 45)              # 8:45 worked
        self.assertEqual((row.status, row.overtime_minutes), (AttendanceDay.PRESENT, 45))   # beyond 8:00
        self.assertEqual((row.in_time, row.out_time), (at(D, 8, 0), at(D, 17, 30)))

    def test_two_punches_have_no_break_and_work_as_before(self):
        row = self.punch((8, 0), (17, 30))
        self.assertEqual((row.break_start, row.break_end, row.break_minutes), (None, None, 0))
        self.assertEqual(row.worked_minutes, 9 * 60 + 30)
        self.assertEqual(row.status, AttendanceDay.PRESENT)

    def test_a_missing_break_punch_sends_the_day_for_review(self):
        row = self.punch((8, 0), (12, 30), (17, 30))                         # three punches
        self.assertEqual(row.status, AttendanceDay.REVIEW)
        self.assertIn('break punch is missing', row.remarks)
        self.assertEqual(row.break_minutes, 0)

    def test_a_very_long_break_is_sent_for_review(self):
        row = self.punch((8, 0), (11, 0), (15, 0), (17, 30))                 # four hours away
        self.assertEqual(row.status, AttendanceDay.REVIEW)
        self.assertIn('Break of 4:00', row.remarks)
        self.assertEqual(row.break_minutes, 240)

    def test_more_than_four_punches_use_the_first_break_only(self):
        row = self.punch((8, 0), (12, 30), (13, 0), (15, 30), (15, 40), (17, 30))
        self.assertEqual((row.break_start, row.break_end, row.break_minutes), (at(D, 12, 30), at(D, 13, 0), 30))

    def test_a_double_tap_is_not_mistaken_for_a_break_punch(self):
        row = self.punch((8, 0), (8, 1), (17, 30))                           # the 8:01 tap is the same punch
        self.assertEqual((row.break_minutes, row.status), (0, AttendanceDay.PRESENT))

    def test_the_break_of_a_night_shift_is_found_too(self):
        times = [at(D, 20, 0), at(D + datetime.timedelta(days=1), 0, 45),
                 at(D + datetime.timedelta(days=1), 1, 30), at(D + datetime.timedelta(days=1), 5, 0)]
        row = self.punch(*times)
        self.assertEqual((row.shift, row.break_minutes), ('Night', 45))
        self.assertEqual(row.worked_minutes, 9 * 60 - 45)

    def test_a_half_day_is_judged_on_the_time_worked_not_the_time_there(self):
        row = self.punch((8, 0), (10, 30), (11, 30), (13, 0))                # 5:00 there, 1:00 break: 4:00 worked
        self.assertEqual((row.worked_minutes, row.status), (240, AttendanceDay.HALF))
        row = self.punch((8, 0), (10, 30), (11, 40), (13, 0), day=D + datetime.timedelta(days=1))   # 3:50 worked
        self.assertEqual(row.status, AttendanceDay.REVIEW)                   # under half a day

    def test_break_can_be_only_recorded_and_not_deducted(self):
        with mock.patch.object(rules, 'DEDUCT_BREAK', False):
            row = self.punch((8, 0), (12, 30), (13, 15), (17, 30))
        self.assertEqual(row.break_minutes, 45)
        self.assertEqual(row.worked_minutes, 9 * 60 + 30)                    # break left in

    def test_adding_the_missing_break_punch_fixes_the_day(self):
        row = self.punch((8, 0), (12, 30), (17, 30))
        self.assertEqual(row.status, AttendanceDay.REVIEW)
        row = self.punch((13, 0))
        self.assertEqual((row.status, row.break_minutes), (AttendanceDay.PRESENT, 30))


class BreakAndHandMadeDaysTests(BreakBase):
    def test_a_hand_made_day_has_no_break_and_clearing_it_brings_the_break_back(self):
        row = self.punch((8, 0), (12, 30), (13, 0), (17, 30))
        self.assertEqual(row.break_minutes, 30)
        manual = services.set_day(self.worker, D, AttendanceDay.PRESENT, self.staff,
                                  in_time=at(D, 8, 0), out_time=at(D, 17, 0))
        self.assertEqual((manual.break_minutes, manual.break_start, manual.is_manual), (0, None, True))
        again = services.clear_manual(manual)
        self.assertEqual((again.break_minutes, again.is_manual), (30, False))


class BreakInTheApiTests(BreakBase):
    def test_the_day_rows_carry_the_break(self):
        self.punch((8, 0), (12, 30), (13, 15), (17, 30))
        row = self.api.get(DAYS, {'worker': self.worker.pk, 'date': D.isoformat()}).json()['results'][0]
        self.assertEqual((row['break_text'], row['break_minutes']), ('0:45', 45))
        self.assertEqual((row['break_start'][11:16], row['break_end'][11:16]), ('12:30', '13:15'))
        self.assertEqual(row['worked_text'], '8:45')

    def test_the_roster_and_the_person_month_show_it_too(self):
        self.punch((8, 0), (12, 30), (13, 15), (17, 30))
        roster = self.api.get(DAYS + 'roster/', {'date': D.isoformat()}).json()
        mine = next(r for r in roster['rows'] if r['worker'] == self.worker.pk)
        self.assertEqual(mine['day']['break_text'], '0:45')
        person = self.api.get(DAYS + 'person/', {'worker': self.worker.pk, 'month': '2001-03'}).json()
        day = next(d for d in person['days'] if d['date'] == D.isoformat())
        self.assertEqual(day['day']['break_text'], '0:45')
        self.assertEqual([p['punched_at'][11:16] for p in day['punches']], ['08:00', '12:30', '13:15', '17:30'])

    def test_a_day_without_break_has_empty_break_text(self):
        self.punch((8, 0), (17, 30))
        row = self.api.get(DAYS, {'worker': self.worker.pk, 'date': D.isoformat()}).json()['results'][0]
        self.assertEqual((row['break_text'], row['break_start']), ('', None))
