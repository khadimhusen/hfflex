"""The six shifts, a worker's own shift, and what overtime is measured against."""
import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from attendance import services, shifts
from attendance.models import AttendanceDay, ShiftAssignment
from employee.models import Worker

DAYS = '/api/attendance/days/'
D = datetime.date(2001, 3, 5)
NEXT = D + datetime.timedelta(days=1)


def at(day, hour, minute=0):
    return datetime.datetime.combine(day, datetime.time(hour, minute))


class ShiftTableTests(TestCase):
    def test_the_six_shifts_and_their_times(self):
        times = {s.key: (shifts.times_text(s), s.minutes) for s in shifts.SHIFTS}
        self.assertEqual(times, {
            'Day': ('08:00–20:00', 720), 'Night': ('20:00–08:00', 720),
            '1st': ('08:00–16:00', 480), '2nd': ('16:00–00:00', 480), '3rd': ('00:00–08:00', 480),
            'General': ('09:00–18:00', 540)})
        self.assertEqual([key for key, _ in shifts.CHOICES], ['Day', 'Night', '1st', '2nd', '3rd', 'General'])

    def test_scheduled_minutes_of_an_unknown_name_is_none(self):
        self.assertIsNone(shifts.scheduled_minutes(''))
        self.assertIsNone(shifts.scheduled_minutes('Graveyard'))


class ShiftBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('shstaff', 'a@example.com', 'x', is_staff=True)
        cls.plain = User.objects.create_user('shplain', 'b@example.com', 'x')
        cls.worker = Worker.objects.create(worker_name='SH WORKER', emp_code='5601',
                                           date_of_join=datetime.date(2000, 1, 1))

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.staff)

    def on(self, shift):
        Worker.objects.filter(pk=self.worker.pk).update(default_shift=shift)
        self.worker.refresh_from_db()

    def punch(self, *times, day=D):
        services.record_punches([{'emp_code': '5601', 'punched_at': at(day, *t) if isinstance(t, tuple) else t}
                                 for t in times])
        return AttendanceDay.objects.get(worker=self.worker, date=day)


class ShiftFromThePunchesTests(ShiftBase):
    def test_a_worker_with_no_shift_keeps_the_old_guess_and_the_eight_hour_overtime(self):
        row = self.punch((8, 0), (17, 30))
        self.assertEqual((row.shift, row.overtime_minutes), ('Day', 90))

    def test_general_overtime_is_beyond_nine_hours(self):
        self.on('General')
        row = self.punch((9, 0), (19, 0))
        self.assertEqual((row.shift, row.worked_minutes, row.overtime_minutes), ('General', 600, 60))

    def test_a_twelve_hour_day_shift_is_not_all_overtime_after_eight(self):
        self.on('Day')
        row = self.punch((8, 0), (20, 30))
        self.assertEqual((row.shift, row.worked_minutes, row.overtime_minutes), ('Day', 750, 30))

    def test_a_first_shift_is_eight_hours(self):
        self.on('1st')
        row = self.punch((8, 0), (16, 30))
        self.assertEqual((row.shift, row.overtime_minutes), ('1st', 30))

    def test_a_second_shift_that_ends_at_midnight_is_one_day(self):
        self.on('2nd')
        row = self.punch(at(D, 16, 0), at(NEXT, 0, 20))
        self.assertEqual((row.shift, row.out_time, row.worked_minutes, row.overtime_minutes),
                         ('2nd', at(NEXT, 0, 20), 500, 20))

    def test_the_break_still_comes_off_before_overtime(self):
        self.on('General')
        row = self.punch((9, 0), (13, 0), (13, 45), (19, 0))
        self.assertEqual((row.worked_minutes, row.overtime_minutes), (600 - 45, 15))

    def test_the_shift_does_not_change_what_counts_as_present(self):
        self.on('Day')
        row = self.punch((8, 0), (15, 30))                  # 7:30 of a 12-hour shift
        self.assertEqual(row.status, AttendanceDay.PRESENT)
        self.assertEqual(row.overtime_minutes, 0)


class ThirdShiftTests(ShiftBase):
    def test_punching_in_before_midnight_belongs_to_the_next_day(self):
        self.on('3rd')
        services.record_punches([{'emp_code': '5601', 'punched_at': at(D, 23, 55)},
                                 {'emp_code': '5601', 'punched_at': at(NEXT, 8, 5)}])
        self.assertFalse(AttendanceDay.objects.filter(worker=self.worker, date=D).exists())
        row = AttendanceDay.objects.get(worker=self.worker, date=NEXT)
        self.assertEqual((row.shift, row.in_time, row.out_time, row.worked_minutes, row.overtime_minutes),
                         ('3rd', at(D, 23, 55), at(NEXT, 8, 5), 490, 10))

    def test_punching_in_just_after_midnight_is_that_day(self):
        self.on('3rd')
        row = self.punch((0, 3), (8, 0), day=D)
        self.assertEqual((row.shift, row.worked_minutes), ('3rd', 477))

    def test_a_night_shift_worker_at_ten_to_eight_is_not_moved_a_day(self):
        self.on('Night')
        row = self.punch((19, 50), at(NEXT, 8, 0))
        self.assertEqual(row.date, D)

    def test_the_person_page_files_the_early_punch_with_the_right_day(self):
        self.on('3rd')
        services.record_punches([{'emp_code': '5601', 'punched_at': at(D, 23, 55)},
                                 {'emp_code': '5601', 'punched_at': at(NEXT, 8, 5)}])
        by_day = services.punches_by_session_day(self.worker, D, NEXT)
        self.assertEqual(sorted(by_day), [NEXT])
        self.assertEqual(len(by_day[NEXT]), 2)

    def test_punches_added_later_before_midnight_rebuild_the_next_day(self):
        self.on('3rd')
        services.record_punches([{'emp_code': '5601', 'punched_at': at(NEXT, 8, 5)}])
        self.assertEqual(AttendanceDay.objects.get(worker=self.worker, date=NEXT).status, AttendanceDay.REVIEW)
        services.record_punches([{'emp_code': '5601', 'punched_at': at(D, 23, 55)}])      # touches D only
        row = AttendanceDay.objects.get(worker=self.worker, date=NEXT)
        self.assertEqual((row.status, row.worked_minutes), (AttendanceDay.PRESENT, 490))


class ShiftByHandTests(ShiftBase):
    def test_a_hand_made_day_uses_the_workers_shift(self):
        self.on('General')
        row = services.set_day(self.worker, D, AttendanceDay.PRESENT, self.staff, in_time=at(D, 9), out_time=at(D, 19))
        self.assertEqual((row.shift, row.overtime_minutes), ('General', 60))

    def test_a_shift_chosen_for_the_day_wins(self):
        self.on('General')
        row = services.set_day(self.worker, D, AttendanceDay.PRESENT, self.staff, in_time=at(D, 9), out_time=at(D, 19),
                               shift='1st')
        self.assertEqual((row.shift, row.overtime_minutes), ('1st', 120))

    def test_without_any_shift_it_is_still_the_guess_and_eight_hours(self):
        row = services.set_day(self.worker, D, AttendanceDay.PRESENT, self.staff, in_time=at(D, 8), out_time=at(D, 17))
        self.assertEqual((row.shift, row.overtime_minutes), ('Day', 60))

    def test_a_day_off_has_no_shift(self):
        self.on('2nd')
        row = services.set_day(self.worker, D, AttendanceDay.LEAVE, self.staff)
        self.assertEqual(row.shift, '')


class ShiftInTheApiTests(ShiftBase):
    def test_the_day_form_accepts_every_shift(self):
        for key in ('Day', 'Night', '1st', '2nd', '3rd', 'General'):
            reply = self.api.post(DAYS, {'worker': self.worker.pk, 'date': '2001-03-05', 'status': 'present',
                                         'shift': key, 'in_time': '2001-03-05T08:00:00', 'out_time': '2001-03-05T17:00:00'},
                                  format='json')
            self.assertEqual(reply.status_code, 201, (key, reply.content))
            self.assertEqual(reply.data['shift'], key)

    def test_people_and_person_carry_the_default_shift(self):
        self.on('2nd')
        people = {p['id']: p for p in self.api.get(DAYS + 'people/').data}
        self.assertEqual(people[self.worker.pk]['default_shift'], '2nd')
        person = self.api.get(DAYS + f'person/?worker={self.worker.pk}&month=2001-03').data
        self.assertEqual(person['worker']['default_shift'], '2nd')

    def test_setting_the_shift_works_this_months_days_out_again(self):
        today = datetime.date.today()
        self.on('General')
        row = self.punch((8, 0), (17, 30), day=today)
        self.assertEqual((row.shift, row.overtime_minutes), ('General', 30))
        reply = self.api.post(DAYS + 'set-shift/', {'worker': self.worker.pk, 'shift': '1st'}, format='json')
        self.assertEqual((reply.status_code, reply.data['default_shift']), (200, '1st'))
        self.assertEqual(reply.data['rows_changed'], 1)
        row.refresh_from_db()
        self.assertEqual((row.shift, row.overtime_minutes), ('1st', 90))
        self.worker.refresh_from_db()
        self.assertEqual(self.worker.default_shift, '1st')

    def test_a_day_corrected_by_hand_is_left_alone(self):
        today = datetime.date.today()
        self.on('General')
        services.set_day(self.worker, today, AttendanceDay.PRESENT, self.staff, in_time=at(today, 9), out_time=at(today, 19))
        self.api.post(DAYS + 'set-shift/', {'worker': self.worker.pk, 'shift': '1st'}, format='json')
        self.assertEqual(AttendanceDay.objects.get(worker=self.worker, date=today).shift, 'General')

    def test_a_blank_shift_clears_it(self):
        self.on('2nd')
        reply = self.api.post(DAYS + 'set-shift/', {'worker': self.worker.pk, 'shift': ''}, format='json')
        self.assertEqual((reply.status_code, reply.data['default_shift']), (200, ''))

    def test_an_unknown_shift_or_worker_is_refused(self):
        bad = self.api.post(DAYS + 'set-shift/', {'worker': self.worker.pk, 'shift': 'Graveyard'}, format='json')
        self.assertEqual(bad.status_code, 400)
        none = self.api.post(DAYS + 'set-shift/', {'worker': 0, 'shift': '1st'}, format='json')
        self.assertEqual(none.status_code, 400)

    def test_only_staff_can_set_it(self):
        api = APIClient()
        api.force_authenticate(self.plain)
        reply = api.post(DAYS + 'set-shift/', {'worker': self.worker.pk, 'shift': '1st'}, format='json')
        self.assertIn(reply.status_code, (403, 404))           # the attendance screens are hidden from everyone else
        self.worker.refresh_from_db()
        self.assertEqual(self.worker.default_shift, '')


def day(n):
    """The date n days after D (D is a Monday)."""
    return D + datetime.timedelta(days=n)


class ShiftRangeTests(ShiftBase):
    """A shift is given for a range of dates. A day in the range takes it; a day outside every
    range takes the shift of the last entry before it; before the first entry it is the usual shift."""

    def give(self, first, last, shift, workers=None):
        return services.assign_shift(workers or [self.worker], day(first), day(last), shift, self.staff)

    def spans(self):
        return [(e.from_date, e.to_date, e.shift) for e in ShiftAssignment.objects.filter(worker=self.worker)
                .order_by('from_date')]

    def shift_on(self, n):
        return services.shift_lookup(self.worker, day(n), day(n))(day(n))

    def test_a_day_in_the_range_takes_its_shift(self):
        self.on('General')
        self.give(0, 6, '1st')
        self.assertEqual([self.shift_on(n) for n in (0, 3, 6)], ['1st', '1st', '1st'])

    def test_a_day_after_the_range_takes_the_last_entrys_shift(self):
        self.on('General')
        self.give(0, 6, '1st')
        self.assertEqual([self.shift_on(n) for n in (7, 8, 400)], ['1st', '1st', '1st'])

    def test_a_day_before_the_first_entry_takes_the_usual_shift(self):
        self.on('General')
        self.give(10, 16, '1st')
        self.assertEqual([self.shift_on(n) for n in (-30, 0, 9)], ['General', 'General', 'General'])
        self.assertEqual(self.shift_on(10), '1st')

    def test_between_two_entries_it_is_the_earlier_and_after_both_the_later(self):
        self.give(0, 6, '1st')
        self.give(14, 20, '2nd')
        self.assertEqual([self.shift_on(n) for n in (6, 7, 13, 14, 20, 21, 90)],
                         ['1st', '1st', '1st', '2nd', '2nd', '2nd', '2nd'])

    def test_no_entry_and_no_usual_shift_leaves_the_shift_to_be_guessed(self):
        self.assertEqual(self.shift_on(0), '')
        row = self.punch((8, 0), (17, 30))
        self.assertEqual((row.shift, row.overtime_minutes), ('Day', 90))

    def test_a_new_entry_inside_an_old_one_splits_it(self):
        self.give(0, 20, '1st')
        self.give(5, 7, '2nd')
        self.assertEqual(self.spans(), [(day(0), day(4), '1st'), (day(5), day(7), '2nd'), (day(8), day(20), '1st')])

    def test_a_new_entry_over_the_start_of_an_old_one_cuts_it_back(self):
        self.give(10, 20, '1st')
        self.give(5, 12, '2nd')
        self.assertEqual(self.spans(), [(day(5), day(12), '2nd'), (day(13), day(20), '1st')])

    def test_a_new_entry_over_the_end_of_an_old_one_shortens_it(self):
        self.give(5, 15, '1st')
        self.give(12, 20, '2nd')
        self.assertEqual(self.spans(), [(day(5), day(11), '1st'), (day(12), day(20), '2nd')])

    def test_a_new_entry_that_covers_an_old_one_replaces_it(self):
        self.give(8, 10, '1st')
        self.give(5, 20, '2nd')
        self.assertEqual(self.spans(), [(day(5), day(20), '2nd')])

    def test_one_day_ranges_and_touching_ranges_are_fine(self):
        self.give(5, 5, '1st')
        self.give(6, 6, '2nd')
        self.assertEqual(self.spans(), [(day(5), day(5), '1st'), (day(6), day(6), '2nd')])

    def conflicts(self, first, last, workers=None):
        return [(c['entry'].from_date, c['entry'].to_date, c['entry'].shift, c['kept'])
                for c in services.shift_conflicts(workers or [self.worker], day(first), day(last))]

    def test_the_overlaps_say_what_each_old_entry_would_keep(self):
        self.give(0, 20, '1st')                                         # a new 5-7 would split it
        self.assertEqual(self.conflicts(5, 7), [(day(0), day(20), '1st', [(day(0), day(4)), (day(8), day(20))])])
        self.assertEqual(self.conflicts(15, 30), [(day(0), day(20), '1st', [(day(0), day(14))])])      # cut at the end
        self.assertEqual(self.conflicts(-5, 4), [(day(0), day(20), '1st', [(day(5), day(20))])])       # cut at the start
        self.assertEqual(self.conflicts(-5, 30), [(day(0), day(20), '1st', [])])                       # replaced

    def test_no_overlap_means_no_conflict_and_asking_changes_nothing(self):
        self.give(0, 6, '1st')
        self.assertEqual(self.conflicts(7, 13), [])
        self.assertEqual(self.conflicts(-9, -1), [])
        self.conflicts(0, 6)
        self.assertEqual(self.spans(), [(day(0), day(6), '1st')])

    def test_the_overlaps_are_for_each_worker_asked_about(self):
        other = Worker.objects.create(worker_name='SH OTHER', emp_code='5602', date_of_join=datetime.date(2000, 1, 1))
        self.give(0, 6, '1st')
        self.give(0, 6, '2nd', workers=[other])
        self.assertEqual({c[2] for c in self.conflicts(3, 4, [self.worker, other])}, {'1st', '2nd'})
        self.assertEqual({c[2] for c in self.conflicts(3, 4, [other])}, {'2nd'})

    def test_asking_about_a_backwards_range_is_refused(self):
        with self.assertRaises(services.AttendanceError):
            self.conflicts(5, 4)

    def test_a_bad_range_or_shift_is_refused_and_nothing_is_saved(self):
        with self.assertRaises(services.AttendanceError):
            self.give(5, 4, '1st')
        with self.assertRaises(services.AttendanceError):
            self.give(0, 6, 'Graveyard')
        with self.assertRaises(services.AttendanceError):
            self.give(0, 6, '')
        self.assertEqual(self.spans(), [])

    def test_giving_a_shift_works_the_days_out_again_including_those_carried_after_it(self):
        self.on('General')
        early = self.punch((8, 0), (17, 30), day=day(0))
        late = self.punch((8, 0), (17, 30), day=day(30))
        self.assertEqual((early.shift, early.overtime_minutes), ('General', 30))
        self.assertEqual(self.give(0, 6, '1st'), 2)
        early.refresh_from_db(); late.refresh_from_db()
        self.assertEqual((early.shift, early.overtime_minutes), ('1st', 90))
        self.assertEqual((late.shift, late.overtime_minutes), ('1st', 90))              # carried on

    def test_a_day_before_the_range_is_not_touched(self):
        self.on('General')
        before = self.punch((8, 0), (17, 30), day=day(-10))
        self.give(0, 6, '1st')
        before.refresh_from_db()
        self.assertEqual(before.shift, 'General')

    def test_a_day_corrected_by_hand_is_left_alone(self):
        self.on('General')
        services.set_day(self.worker, day(0), AttendanceDay.PRESENT, self.staff, in_time=at(D, 9), out_time=at(D, 19))
        self.give(0, 6, '1st')
        self.assertEqual(AttendanceDay.objects.get(worker=self.worker, date=D).shift, 'General')

    def test_removing_an_entry_sends_its_days_back_to_the_entry_before(self):
        self.on('General')
        self.give(0, 6, '1st')
        self.give(14, 20, '2nd')
        row = self.punch((8, 0), (17, 30), day=day(16))
        self.assertEqual(row.shift, '2nd')
        late = ShiftAssignment.objects.get(worker=self.worker, shift='2nd')
        services.remove_assignment(late)
        row.refresh_from_db()
        self.assertEqual(row.shift, '1st')
        services.remove_assignment(ShiftAssignment.objects.get(worker=self.worker))
        row.refresh_from_db()
        self.assertEqual(row.shift, 'General')

    def test_a_hand_made_day_takes_the_shift_of_its_range(self):
        self.give(0, 6, '1st')
        row = services.set_day(self.worker, D, AttendanceDay.PRESENT, self.staff, in_time=at(D, 8), out_time=at(D, 17))
        self.assertEqual((row.shift, row.overtime_minutes), ('1st', 60))

    def test_several_workers_at_once(self):
        other = Worker.objects.create(worker_name='SH OTHER', emp_code='5602', date_of_join=datetime.date(2000, 1, 1))
        self.give(0, 6, '2nd', workers=[self.worker, other])
        self.assertEqual(ShiftAssignment.objects.filter(worker__in=[self.worker, other], shift='2nd').count(), 2)

    def test_a_range_in_the_future_changes_no_days(self):
        future = datetime.date.today() + datetime.timedelta(days=30)
        self.assertEqual(services.assign_shift([self.worker], future, future + datetime.timedelta(days=6), '2nd'), 0)

    def test_a_third_shift_range_files_the_sunday_night_punch_with_monday(self):
        sunday = day(-1)
        services.record_punches([{'emp_code': '5601', 'punched_at': at(sunday, 23, 55)},
                                 {'emp_code': '5601', 'punched_at': at(D, 8, 5)}])
        self.assertTrue(AttendanceDay.objects.filter(worker=self.worker, date=sunday).exists())     # no shift yet
        self.give(0, 6, '3rd')
        self.assertFalse(AttendanceDay.objects.filter(worker=self.worker, date=sunday).exists())
        row = AttendanceDay.objects.get(worker=self.worker, date=D)
        self.assertEqual((row.shift, row.in_time, row.overtime_minutes), ('3rd', at(sunday, 23, 55), 10))
        services.remove_assignment(ShiftAssignment.objects.get(worker=self.worker))                 # and back again
        self.assertTrue(AttendanceDay.objects.filter(worker=self.worker, date=sunday).exists())
        self.assertFalse(AttendanceDay.objects.filter(worker=self.worker, date=D).exists())

    def test_the_person_page_uses_the_range_too(self):
        self.give(0, 6, '3rd')
        services.record_punches([{'emp_code': '5601', 'punched_at': at(day(-1), 23, 55)},
                                 {'emp_code': '5601', 'punched_at': at(D, 8, 5)}])
        self.assertEqual(sorted(services.punches_by_session_day(self.worker, day(-1), D)), [D])


class ShiftsOnADayTests(ShiftBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.usual = Worker.objects.create(worker_name='SH USUAL', emp_code='5602', default_shift='General',
                                          date_of_join=datetime.date(2000, 1, 1))
        cls.none = Worker.objects.create(worker_name='SH NONE', emp_code='5603', date_of_join=datetime.date(2000, 1, 1))
        cls.left = Worker.objects.create(worker_name='SH LEFT', emp_code='5604', date_of_join=datetime.date(2000, 1, 1),
                                         date_of_releave=day(-1))

    def rows(self, n):
        return {r['worker'].pk: r for r in services.shifts_on(day(n))}

    def test_each_worker_with_the_shift_they_have_and_why(self):
        services.assign_shift([self.worker], day(0), day(6), '2nd')
        inside, after = self.rows(3), self.rows(10)
        self.assertEqual((inside[self.worker.pk]['shift'], inside[self.worker.pk]['source']), ('2nd', 'range'))
        self.assertEqual((after[self.worker.pk]['shift'], after[self.worker.pk]['source']), ('2nd', 'carried'))
        self.assertEqual((inside[self.usual.pk]['shift'], inside[self.usual.pk]['source']), ('General', 'usual'))
        self.assertEqual((inside[self.none.pk]['shift'], inside[self.none.pk]['source']), ('', ''))

    def test_before_the_first_entry_it_is_the_usual_shift(self):
        services.assign_shift([self.usual], day(10), day(16), '1st')
        row = self.rows(3)[self.usual.pk]
        self.assertEqual((row['shift'], row['source'], row['entry']), ('General', 'usual', None))

    def test_someone_who_had_left_is_not_listed(self):
        self.assertNotIn(self.left.pk, self.rows(0))
        self.assertIn(self.left.pk, self.rows(-5))


class ShiftRangeApiTests(ShiftBase):
    def post(self, path, body, api=None):
        return (api or self.api).post(DAYS + path, body, format='json')

    def mine(self):
        return ShiftAssignment.objects.filter(worker=self.worker)

    def assign(self, **changes):
        body = {'workers': [self.worker.pk], 'from_date': '2001-03-05', 'to_date': '2001-03-11', 'shift': '2nd'}
        return self.post('assign-shift/', {**body, **changes})

    def test_giving_a_shift(self):
        self.on('General')
        reply = self.assign()
        self.assertEqual((reply.status_code, reply.data['assigned']), (200, 1))
        entry = ShiftAssignment.objects.get(worker=self.worker)
        self.assertEqual((entry.from_date, entry.to_date, entry.shift, entry.edited_by), (D, day(6), '2nd', self.staff))

    def test_bad_input_is_refused(self):
        self.assertEqual(self.assign(shift='Graveyard').status_code, 400)
        self.assertEqual(self.assign(shift='').status_code, 400)
        self.assertEqual(self.assign(to_date='2001-03-04').status_code, 400)
        self.assertEqual(self.assign(from_date='soon').status_code, 400)
        self.assertEqual(self.assign(workers=[]).status_code, 400)
        self.assertEqual(self.assign(workers=[0]).status_code, 400)
        self.assertEqual(self.assign(workers='1').status_code, 400)
        self.assertFalse(self.mine().exists())

    def test_asking_what_a_new_shift_would_overwrite(self):
        self.assign(from_date='2001-03-01', to_date='2001-03-20', shift='1st')
        body = {'workers': [self.worker.pk], 'from_date': '2001-03-05', 'to_date': '2001-03-07'}
        reply = self.post('shift-overlaps/', body)
        self.assertEqual(reply.status_code, 200)
        (overlap,) = reply.data['overlaps']
        self.assertEqual((overlap['worker_name'], overlap['from_date'], overlap['to_date'], overlap['shift']),
                         ('SH WORKER', '2001-03-01', '2001-03-20', '1st'))
        self.assertEqual(overlap['kept'], [{'from_date': '2001-03-01', 'to_date': '2001-03-04'},
                                           {'from_date': '2001-03-08', 'to_date': '2001-03-20'}])
        self.assertEqual(self.post('shift-overlaps/', {**body, 'from_date': '2001-04-01',
                                                       'to_date': '2001-04-02'}).data['overlaps'], [])
        self.assertEqual(self.mine().count(), 1)                      # asking saved nothing

    def test_asking_with_bad_input_is_refused(self):
        body = {'workers': [self.worker.pk], 'from_date': '2001-03-05', 'to_date': '2001-03-07'}
        self.assertEqual(self.post('shift-overlaps/', {**body, 'to_date': '2001-03-04'}).status_code, 400)
        self.assertEqual(self.post('shift-overlaps/', {**body, 'workers': []}).status_code, 400)
        self.assertEqual(self.post('shift-overlaps/', {**body, 'from_date': 'soon'}).status_code, 400)

    def test_the_shifts_on_a_date(self):
        self.on('General')
        self.assign()
        data = self.api.get(DAYS + 'shifts-on/?date=2001-03-08').data
        row = next(r for r in data['rows'] if r['worker'] == self.worker.pk)
        self.assertEqual((row['shift'], row['source'], row['usual']), ('2nd', 'range', 'General'))
        self.assertEqual((row['entry']['from_date'], row['entry']['to_date']), ('2001-03-05', '2001-03-11'))
        later = self.api.get(DAYS + 'shifts-on/?date=2001-04-08').data
        self.assertEqual(next(r for r in later['rows'] if r['worker'] == self.worker.pk)['source'], 'carried')
        self.assertEqual(self.api.get(DAYS + 'shifts-on/?date=soon').status_code, 400)

    def test_the_list_of_ranges_and_taking_one_away(self):
        self.assign()
        self.assign(from_date='2001-03-12', to_date='2001-03-18', shift='3rd')
        ranges = self.api.get(DAYS + f'shift-ranges/?worker={self.worker.pk}').data
        self.assertEqual([(r['from_date'], r['to_date'], r['shift']) for r in ranges],
                         [('2001-03-12', '2001-03-18', '3rd'), ('2001-03-05', '2001-03-11', '2nd')])
        self.assertEqual(self.api.get(DAYS + 'shift-ranges/?worker=0').data, [])
        reply = self.post('remove-shift-range/', {'id': ranges[0]['id']})
        self.assertEqual(reply.status_code, 200)
        self.assertEqual(self.mine().count(), 1)
        self.assertEqual(self.post('remove-shift-range/', {'id': 0}).status_code, 400)

    def test_only_staff_can_use_them(self):
        api = APIClient()
        api.force_authenticate(self.plain)
        replies = [
            api.get(DAYS + 'shifts-on/?date=2001-03-05'),
            api.get(DAYS + 'shift-ranges/'),
            self.post('shift-overlaps/', {'workers': [self.worker.pk], 'from_date': '2001-03-05',
                                          'to_date': '2001-03-11'}, api),
            self.post('assign-shift/', {'workers': [self.worker.pk], 'from_date': '2001-03-05',
                                        'to_date': '2001-03-11', 'shift': '2nd'}, api),
            self.post('remove-shift-range/', {'id': 1}, api),
        ]
        for reply in replies:
            self.assertIn(reply.status_code, (403, 404))
        self.assertFalse(self.mine().exists())
