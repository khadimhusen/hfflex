import datetime
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import load_workbook
from rest_framework.test import APIClient

from attendance import rules, services
from attendance.models import AttendanceDay, PunchLog
from employee.models import Worker

PUNCHES = '/api/attendance/punches/'
DAYS = '/api/attendance/days/'
D = datetime.date(2001, 3, 5)                     # old dates: nothing real can clash with them


def at(day, hour, minute=0):
    return datetime.datetime.combine(day, datetime.time(hour, minute))


def worker(name, code, joined=datetime.date(2000, 1, 1), left=None, active=True):
    return Worker.objects.create(worker_name=name, emp_code=code, date_of_join=joined, date_of_releave=left,
                                 is_active=active)


class AttendanceBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('attstaff', 'a@example.com', 'x', is_staff=True)
        cls.plain = User.objects.create_user('attplain', 'b@example.com', 'x')
        cls.ravi = worker('TEST Ravi', 'T9001')
        cls.anita = worker('TEST Anita', 'T9002')

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.staff)

    def punch(self, w, *when):
        services.record_punches([{'emp_code': w.emp_code, 'punched_at': t} for t in when])

    def day(self, w, d=D):
        return AttendanceDay.objects.filter(worker=w, date=d).first()


class CodeAndMatchingTests(AttendanceBase):
    def test_leading_zeros_and_spaces_do_not_matter(self):
        self.assertEqual(services.clean_code(' 0037 '), '37')
        self.assertEqual(services.clean_code('T9001'), 'T9001')
        self.assertEqual(services.clean_code('000'), '0')
        self.assertEqual(services.clean_code(''), '')

    def test_a_punch_finds_its_worker_by_code(self):
        w = worker('TEST Zero', 'T0042')
        result = services.record_punches([{'emp_code': 'T0042', 'punched_at': at(D, 8)}])
        self.assertEqual((result['created'], result['unmatched']), (1, 0))
        self.assertEqual(PunchLog.objects.get(emp_code='T0042').worker, w)

    def test_an_unknown_code_is_kept_but_unmatched(self):
        result = services.record_punches([{'emp_code': 'T7777', 'punched_at': at(D, 8)}])
        self.assertEqual((result['created'], result['unmatched']), (1, 1))
        self.assertIsNone(PunchLog.objects.get(emp_code='T7777').worker)
        self.assertEqual(AttendanceDay.objects.filter(date=D).count(), 0)

    def test_a_code_reused_after_someone_left_goes_to_who_was_employed_that_day(self):
        old = worker('TEST Old', 'T9100', joined=datetime.date(1999, 1, 1), left=datetime.date(2001, 1, 31), active=False)
        new = worker('TEST New', 'T9100', joined=datetime.date(2001, 2, 1))
        matcher = services.WorkerMatcher()
        self.assertEqual(matcher.find('T9100', datetime.date(2001, 1, 15)), old)
        self.assertEqual(matcher.find('T9100', D), new)

    def test_two_workers_employed_the_same_day_with_one_code_is_left_for_a_person(self):
        worker('TEST Twin A', 'T9200')
        worker('TEST Twin B', 'T9200')
        self.assertIsNone(services.WorkerMatcher().find('T9200', D))

    def test_a_punch_before_the_worker_joined_is_not_guessed(self):
        worker('TEST Late', 'T9300', joined=datetime.date(2001, 6, 1))
        self.assertIsNone(services.WorkerMatcher().find('T9300', D))


class RecordingPunchesTests(AttendanceBase):
    def test_the_same_punches_twice_change_nothing(self):
        rows = [{'emp_code': 'T9001', 'punched_at': at(D, 8)}, {'emp_code': 'T9001', 'punched_at': at(D, 17)}]
        first = services.record_punches(rows)
        second = services.record_punches(rows)
        self.assertEqual((first['created'], first['duplicates']), (2, 0))
        self.assertEqual((second['created'], second['duplicates']), (0, 2))
        self.assertEqual(PunchLog.objects.filter(emp_code='T9001').count(), 2)

    def test_a_repeated_row_inside_one_batch_counts_once(self):
        result = services.record_punches([{'emp_code': 'T9001', 'punched_at': at(D, 8)}] * 3)
        self.assertEqual((result['received'], result['created'], result['duplicates']), (3, 1, 2))

    def test_bad_rows_are_reported_not_fatal(self):
        result = services.record_punches([
            {'emp_code': '', 'punched_at': at(D, 8)}, {'emp_code': 'T9001', 'punched_at': 'yesterday-ish'},
            {'emp_code': 'T9001', 'punched_at': at(D, 9)}])
        self.assertEqual((result['created'], result['invalid']), (1, 2))
        self.assertEqual(len(result['errors']), 2)

    def test_the_text_formats_the_reader_software_uses(self):
        result = services.record_punches([
            {'emp_code': 'T9001', 'punched_at': '05/03/2001 08:00:15'}, {'emp_code': 'T9001', 'punched_at': '05/03/2001_09:30'},
            {'emp_code': 'T9001', 'punched_at': '2001-03-05T10:00:00'}, {'emp_code': 'T9001', 'punched_at': '2001-03-05 11:00'}])
        self.assertEqual(result['created'], 4)
        self.assertEqual(PunchLog.objects.filter(emp_code='T9001').order_by('punched_at').first().punched_at, at(D, 8).replace(second=15))


class BuildingDaysTests(AttendanceBase):
    def test_a_full_day_is_present_with_overtime_after_eight_hours(self):
        self.punch(self.ravi, at(D, 8, 0), at(D, 18, 0))
        row = self.day(self.ravi)
        self.assertEqual((row.status, row.shift, row.worked_minutes, row.overtime_minutes), ('present', 'Day', 600, 120))
        self.assertEqual((row.in_time, row.out_time), (at(D, 8), at(D, 18)))

    def test_a_short_day_is_a_half_day(self):
        self.punch(self.ravi, at(D, 8), at(D, 13))
        self.assertEqual(self.day(self.ravi).status, 'half')

    def test_a_very_short_stay_needs_review(self):
        self.punch(self.ravi, at(D, 8), at(D, 9))
        row = self.day(self.ravi)
        self.assertEqual(row.status, 'review')
        self.assertIn('short', row.remarks)

    def test_one_punch_alone_needs_review_and_has_no_out_time(self):
        self.punch(self.ravi, at(D, 8))
        row = self.day(self.ravi)
        self.assertEqual((row.status, row.out_time, row.worked_minutes), ('review', None, 0))

    def test_the_thresholds_come_from_rules(self):
        self.assertEqual((rules.FULL_DAY_MINUTES, rules.HALF_DAY_MINUTES, rules.STANDARD_DAY_MINUTES), (420, 240, 480))

    def test_a_night_shift_across_midnight_is_one_day_dated_when_it_started(self):
        self.punch(self.ravi, at(D, 20, 0), at(D + datetime.timedelta(days=1), 8, 0))
        row = self.day(self.ravi)
        self.assertEqual((row.status, row.shift, row.worked_minutes, row.overtime_minutes), ('present', 'Night', 720, 240))
        self.assertEqual(row.out_time, at(D + datetime.timedelta(days=1), 8))
        self.assertIsNone(self.day(self.ravi, D + datetime.timedelta(days=1)), 'the morning out-punch is not a new day')

    def test_back_to_back_night_shifts_stay_separate_days(self):
        nxt = D + datetime.timedelta(days=1)
        self.punch(self.ravi, at(D, 20), at(nxt, 8), at(nxt, 20), at(nxt + datetime.timedelta(days=1), 8))
        self.assertEqual(self.day(self.ravi).out_time, at(nxt, 8))
        self.assertEqual(self.day(self.ravi, nxt).in_time, at(nxt, 20))

    def test_a_double_tap_is_one_punch(self):
        self.punch(self.ravi, at(D, 8, 0), at(D, 8, 1), at(D, 17, 0), at(D, 17, 1))
        row = self.day(self.ravi)
        self.assertEqual((row.in_time, row.out_time, row.worked_minutes), (at(D, 8), at(D, 17), 540))

    def test_a_late_punch_updates_the_row(self):
        self.punch(self.ravi, at(D, 8))
        self.assertEqual(self.day(self.ravi).status, 'review')
        self.punch(self.ravi, at(D, 17))
        self.assertEqual((self.day(self.ravi).status, self.day(self.ravi).worked_minutes), ('present', 540))
        self.assertEqual(AttendanceDay.objects.filter(worker=self.ravi, date=D).count(), 1)

    def test_workers_do_not_mix(self):
        self.punch(self.ravi, at(D, 8), at(D, 17))
        self.punch(self.anita, at(D, 9), at(D, 14))
        self.assertEqual((self.day(self.ravi).status, self.day(self.anita).status), ('present', 'half'))

    def test_removing_the_punches_removes_the_row_built_from_them(self):
        self.punch(self.ravi, at(D, 8), at(D, 17))
        PunchLog.objects.filter(worker=self.ravi).delete()
        services.rebuild_days(self.ravi, D, D)
        self.assertIsNone(self.day(self.ravi))


class ByHandTests(AttendanceBase):
    def test_a_hand_set_day_survives_a_rebuild_and_new_punches(self):
        self.punch(self.ravi, at(D, 8), at(D, 17))
        services.set_day(self.ravi, D, 'leave', self.staff, remarks='Fever')
        self.punch(self.ravi, at(D, 18))
        services.rebuild_days(self.ravi, D, D)
        row = self.day(self.ravi)
        self.assertEqual((row.status, row.is_manual, row.remarks), ('leave', True, 'Fever'))

    def test_leave_and_days_off_carry_no_times(self):
        row = services.set_day(self.ravi, D, 'weekly_off', self.staff, in_time=at(D, 8), out_time=at(D, 17))
        self.assertEqual((row.in_time, row.out_time, row.worked_minutes, row.shift), (None, None, 0, ''))

    def test_times_are_worked_out_for_a_corrected_day(self):
        row = services.set_day(self.ravi, D, 'present', self.staff, in_time=at(D, 8), out_time=at(D, 17))
        self.assertEqual((row.worked_minutes, row.overtime_minutes, row.shift), (540, 60, 'Day'))

    def test_out_must_be_after_in(self):
        with self.assertRaises(services.AttendanceError):
            services.set_day(self.ravi, D, 'present', self.staff, in_time=at(D, 17), out_time=at(D, 8))

    def test_an_unknown_status_is_refused(self):
        with self.assertRaises(services.AttendanceError):
            services.set_day(self.ravi, D, 'on_the_moon', self.staff)

    def test_clearing_a_hand_set_day_hands_it_back_to_the_punches(self):
        self.punch(self.ravi, at(D, 8), at(D, 17))
        row = services.set_day(self.ravi, D, 'absent', self.staff)
        back = services.clear_manual(row)
        self.assertEqual((back.status, back.is_manual), ('present', False))

    def test_clearing_with_no_punches_leaves_nothing(self):
        row = services.set_day(self.ravi, D, 'absent', self.staff)
        self.assertIsNone(services.clear_manual(row))


class RosterAndAbsentTests(AttendanceBase):
    def roster_ids(self, day=D):
        return {w.pk for w, _ in services.roster(day)}

    def test_the_roster_is_the_workers_employed_that_day(self):
        left = worker('TEST Gone', 'T9400', left=datetime.date(2001, 3, 1), active=False)
        notyet = worker('TEST Future', 'T9401', joined=datetime.date(2001, 4, 1))
        inactive = worker('TEST Inactive', 'T9402', active=False)
        ids = self.roster_ids()
        self.assertTrue({self.ravi.pk, self.anita.pk} <= ids)
        self.assertFalse({left.pk, notyet.pk, inactive.pk} & ids)

    def test_a_worker_who_has_left_but_has_a_row_still_shows(self):
        left = worker('TEST Gone', 'T9400', left=datetime.date(2001, 3, 1), active=False)
        services.set_day(left, D, 'present', self.staff, in_time=at(D, 8), out_time=at(D, 17))
        self.assertIn(left.pk, self.roster_ids())

    def test_mark_absent_covers_only_those_with_no_row(self):
        self.punch(self.ravi, at(D, 8), at(D, 17))
        services.mark_absent(D, self.staff)
        self.assertEqual(self.day(self.ravi).status, 'present')
        self.assertEqual(self.day(self.anita).status, 'absent')

    def test_a_punch_arriving_later_replaces_an_automatic_absent(self):
        services.mark_absent(D, self.staff)
        self.punch(self.anita, at(D, 8), at(D, 17))
        row = self.day(self.anita)
        self.assertEqual((row.status, row.is_manual), ('present', False))

    def test_a_hand_set_absent_is_not_replaced_by_a_punch(self):
        services.set_day(self.anita, D, 'absent', self.staff, remarks='Told us in advance')
        self.punch(self.anita, at(D, 8), at(D, 17))
        self.assertEqual(self.day(self.anita).status, 'absent')


class MonthSheetTests(AttendanceBase):
    def test_totals_and_paid_days(self):
        for offset, hours in ((0, 9), (1, 9), (2, 5)):             # two present, one half day
            d = D + datetime.timedelta(days=offset)
            self.punch(self.ravi, at(d, 8), at(d, 8 + hours))
        services.set_day(self.ravi, D + datetime.timedelta(days=3), 'leave', self.staff)
        services.set_day(self.ravi, D + datetime.timedelta(days=4), 'absent', self.staff)
        entry = next(e for e in services.month_sheet(2001, 3) if e['worker'].pk == self.ravi.pk)
        self.assertEqual(entry['counts'], {'present': 2, 'half': 1, 'leave': 1, 'absent': 1})
        self.assertEqual(entry['paid_days'], 2 + 1 + 0.5)
        self.assertEqual(entry['worked_minutes'], 540 * 2 + 300)
        self.assertEqual(entry['overtime_minutes'], 60 * 2)

    def test_the_sheet_only_has_that_months_days(self):
        self.punch(self.ravi, at(D, 8), at(D, 17))
        april = next((e for e in services.month_sheet(2001, 4) if e['worker'].pk == self.ravi.pk), None)
        self.assertTrue(april is None or april['days'] == {})


class ApiTests(AttendanceBase):
    def test_only_staff_may_use_it(self):
        self.api.force_authenticate(self.plain)
        for url in (PUNCHES, DAYS, DAYS + 'roster/?date=2001-03-05', DAYS + 'month/?month=2001-03'):
            self.assertIn(self.api.get(url).status_code, (403, 404), url)
        self.api.force_authenticate(None)
        self.assertIn(self.api.get(PUNCHES).status_code, (401, 403, 404))

    def test_bulk_punches_build_the_days(self):
        rows = [{'emp_code': 'T9001', 'punched_at': '2001-03-05T08:00:00'}, {'emp_code': 'T9001', 'punched_at': '2001-03-05T17:00:00'},
                {'emp_code': 'T5555', 'punched_at': '2001-03-05T08:00:00'}]
        data = self.api.post(PUNCHES + 'bulk/', {'source': 'etimeoffice', 'rows': rows}, format='json').json()
        self.assertEqual((data['created'], data['unmatched']), (3, 1))
        self.assertEqual(self.day(self.ravi).status, 'present')
        self.assertEqual(PunchLog.objects.get(emp_code='T5555').source, 'etimeoffice')

    def test_bulk_needs_rows_and_a_known_source(self):
        self.assertEqual(self.api.post(PUNCHES + 'bulk/', {'rows': []}, format='json').status_code, 400)
        self.assertEqual(self.api.post(PUNCHES + 'bulk/', {'source': 'x', 'rows': [{'emp_code': '1'}]}, format='json').status_code, 400)

    def test_a_csv_file_with_the_usual_columns(self):
        csv_text = 'Empcode,PunchDate\nT9001,05/03/2001 08:00:00\nT9001,05/03/2001 17:00:00\n'
        upload = SimpleUploadedFile('punches.csv', csv_text.encode(), content_type='text/csv')
        data = self.api.post(PUNCHES + 'import-csv/', {'file': upload}, format='multipart').json()
        self.assertEqual((data['created'], data['invalid']), (2, 0))
        self.assertEqual(self.day(self.ravi).status, 'present')

    def test_a_csv_with_separate_date_and_time_columns_and_a_bom(self):
        csv_text = '﻿code,date,time\nT9002,2001-03-05,08:00\nT9002,2001-03-05,17:30\n'
        upload = SimpleUploadedFile('p.csv', csv_text.encode('utf-8'), content_type='text/csv')
        data = self.api.post(PUNCHES + 'import-csv/', {'file': upload}, format='multipart').json()
        self.assertEqual(data['created'], 2)
        self.assertEqual(self.day(self.anita).worked_minutes, 570)

    def test_a_csv_upload_must_be_a_file(self):
        self.assertEqual(self.api.post(PUNCHES + 'import-csv/', {}, format='multipart').status_code, 400)

    def test_a_manual_punch(self):
        response = self.api.post(PUNCHES, {'worker': self.ravi.pk, 'punched_at': '2001-03-05T08:00:00', 'note': 'Forgot'}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['source'], 'manual')
        again = self.api.post(PUNCHES, {'worker': self.ravi.pk, 'punched_at': '2001-03-05T08:00:00'}, format='json')
        self.assertEqual(again.status_code, 400)

    def test_deleting_a_punch_updates_the_day(self):
        self.punch(self.ravi, at(D, 8), at(D, 17))
        last = PunchLog.objects.get(worker=self.ravi, punched_at=at(D, 17))
        self.assertEqual(self.api.delete(f'{PUNCHES}{last.pk}/').status_code, 204)
        self.assertEqual(self.day(self.ravi).status, 'review')

    def test_punch_filters(self):
        self.punch(self.ravi, at(D, 8))
        services.record_punches([{'emp_code': 'T4444', 'punched_at': at(D, 9)}])
        ids = lambda **q: {p['emp_code'] for p in self.api.get(PUNCHES, {'date_from': '2001-03-05', 'date_to': '2001-03-05', **q}).json()['results']}
        self.assertEqual(ids(unmatched='true'), {'T4444'})
        self.assertEqual(ids(unmatched='false'), {'T9001'})
        self.assertEqual(ids(search='Ravi'), {'T9001'})

    def test_unmatched_codes_and_relinking(self):
        services.record_punches([{'emp_code': 'T6001', 'punched_at': at(D, 8)}, {'emp_code': 'T6001', 'punched_at': at(D, 17)}])
        listed = {u['emp_code']: u['punches'] for u in self.api.get(PUNCHES + 'unmatched/').json()}
        self.assertEqual(listed['T6001'], 2)
        newcomer = worker('TEST Newcomer', 'T6001')
        result = self.api.post(PUNCHES + 'relink/').json()
        self.assertGreaterEqual(result['attached'], 2)
        self.assertEqual(self.day(newcomer).status, 'present')
        self.assertNotIn('T6001', {u['emp_code'] for u in self.api.get(PUNCHES + 'unmatched/').json()})

    def test_the_roster(self):
        self.punch(self.ravi, at(D, 8), at(D, 17))
        data = self.api.get(DAYS + 'roster/', {'date': '2001-03-05'}).json()
        rows = {r['worker']: r for r in data['rows']}
        self.assertEqual(rows[self.ravi.pk]['day']['status'], 'present')
        self.assertIsNone(rows[self.anita.pk]['day'])
        self.assertEqual(data['counts']['present'], 1)
        self.assertGreaterEqual(data['counts']['not_marked'], 1)

    def test_a_bad_date_is_a_clear_error(self):
        self.assertEqual(self.api.get(DAYS + 'roster/', {'date': '05-03-2001'}).status_code, 400)
        self.assertEqual(self.api.get(DAYS + 'month/', {'month': '2001-13'}).status_code, 400)

    def test_mark_absent_and_not_for_the_future(self):
        data = self.api.post(DAYS + 'mark-absent/', {'date': '2001-03-05'}, format='json').json()
        self.assertGreaterEqual(data['marked_absent'], 2)
        self.assertEqual(self.api.post(DAYS + 'mark-absent/', {'date': '2999-01-01'}, format='json').status_code, 400)

    def test_setting_changing_and_clearing_a_day(self):
        body = {'worker': self.ravi.pk, 'date': '2001-03-05', 'status': 'leave', 'remarks': 'Fever'}
        row = self.api.post(DAYS, body, format='json').json()
        self.assertEqual((row['status'], row['is_manual']), ('leave', True))
        changed = self.api.patch(f'{DAYS}{row["id"]}/', {'status': 'present', 'in_time': '2001-03-05T08:00:00',
                                                          'out_time': '2001-03-05T17:00:00'}, format='json').json()
        self.assertEqual((changed['status'], changed['worked_text'], changed['remarks']), ('present', '9:00', 'Fever'))
        self.assertEqual(self.api.delete(f'{DAYS}{row["id"]}/').status_code, 204)
        self.assertIsNone(self.day(self.ravi))

    def test_a_bad_hand_edit_is_refused(self):
        body = {'worker': self.ravi.pk, 'date': '2001-03-05', 'status': 'present',
                'in_time': '2001-03-05T17:00:00', 'out_time': '2001-03-05T08:00:00'}
        response = self.api.post(DAYS, body, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('after', response.content.decode())

    def test_rebuild_after_the_rules_change(self):
        self.punch(self.ravi, at(D, 8), at(D, 17))
        AttendanceDay.objects.filter(worker=self.ravi).update(status='absent', worked_minutes=0)
        data = self.api.post(DAYS + 'rebuild/', {'date_from': '2001-03-05', 'date_to': '2001-03-06'}, format='json').json()
        self.assertGreaterEqual(data['rows_changed'], 1)
        self.assertEqual(self.day(self.ravi).status, 'present')

    def test_list_filters(self):
        self.punch(self.ravi, at(D, 8), at(D, 17))
        self.punch(self.anita, at(D, 9), at(D, 12))
        names = lambda **q: {r['worker_name'] for r in self.api.get(DAYS, {'date': '2001-03-05', **q}).json()['results']}
        self.assertEqual(names(status='present'), {'TEST Ravi'})
        self.assertEqual(names(status='review'), {'TEST Anita'})
        self.assertEqual(names(search='anita'), {'TEST Anita'})

    def test_the_month_grid(self):
        self.punch(self.ravi, at(D, 8), at(D, 18))
        data = self.api.get(DAYS + 'month/', {'month': '2001-03'}).json()
        self.assertEqual(data['days_in_month'], 31)
        entry = next(r for r in data['rows'] if r['worker'] == self.ravi.pk)
        self.assertEqual(entry['days']['5']['status'], 'present')
        self.assertEqual((entry['worked_text'], entry['overtime_text']), ('10:00', '2:00'))

    def test_the_month_as_excel(self):
        self.punch(self.ravi, at(D, 8), at(D, 18))
        services.set_day(self.anita, D, 'absent', self.staff)
        response = self.api.get(DAYS + 'month-excel/', {'month': '2001-03'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('spreadsheetml', response['Content-Type'])
        self.assertIn('attendance_2001-03.xlsx', response['Content-Disposition'])
        sheet = load_workbook(BytesIO(response.content)).active
        rows = {r[1]: r for r in sheet.iter_rows(min_row=5, values_only=True) if r[1]}
        self.assertEqual(rows['TEST Ravi'][1 + 5], 'P')
        self.assertEqual(rows['TEST Anita'][1 + 5], 'A')
        header = [c.value for c in sheet[4]]
        self.assertEqual(header[:2] + header[-3:], ['Code', 'Worker', 'Worked hrs', 'Overtime hrs', 'Paid days'])

    def test_the_module_flag_for_the_menu(self):
        self.assertTrue(self.api.get('/api/crm/me/').json()['modules']['attendance'])
        self.api.force_authenticate(self.plain)
        self.assertFalse(self.api.get('/api/crm/me/').json()['modules']['attendance'])
