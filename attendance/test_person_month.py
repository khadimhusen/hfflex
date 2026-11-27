"""One worker's month: GET days/person/?worker=&month= and days/people/."""
import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from attendance import services
from attendance.models import AttendanceDay
from employee.models import Worker
from holidaylist.models import Holiday

DAYS = '/api/attendance/days/'
MARCH = '2001-03'


def at(day, hour, minute=0):
    return datetime.datetime.combine(day, datetime.time(hour, minute))


class PersonMonthTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('pmstaff', 'a@example.com', 'x', is_staff=True)
        cls.plain = User.objects.create_user('pmplain', 'b@example.com', 'x')
        cls.worker = Worker.objects.create(worker_name='PM WORKER', emp_code='6601',
                                           date_of_join=datetime.date(2001, 3, 10))
        cls.other = Worker.objects.create(worker_name='PM OTHER', emp_code='6602',
                                          date_of_join=datetime.date(2000, 1, 1))
        cls.left = Worker.objects.create(worker_name='PM LEFT', emp_code='6603', is_active=False,
                                         date_of_join=datetime.date(2000, 1, 1),
                                         date_of_releave=datetime.date(2001, 3, 20))

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.staff)

    def punch(self, worker, day, came=(8, 0), left=(17, 30)):
        services.record_punches([
            {'emp_code': worker.emp_code, 'punched_at': at(day, *came)},
            {'emp_code': worker.emp_code, 'punched_at': at(day, *left)},
        ])

    def person(self, worker=None, month=MARCH):
        response = self.api.get(DAYS + 'person/', {'worker': (worker or self.worker).pk, 'month': month})
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_every_calendar_day_of_the_month_is_listed_in_order(self):
        data = self.person()
        self.assertEqual(data['worker']['name'], 'PM WORKER')
        self.assertEqual(data['month'], MARCH)
        self.assertEqual([d['date'] for d in data['days']][:3], ['2001-03-01', '2001-03-02', '2001-03-03'])
        self.assertEqual(len(data['days']), 31)
        self.assertEqual(data['days'][0]['weekday'], 'Thu')            # 1 March 2001 was a Thursday

    def test_days_before_joining_are_not_employed_and_a_day_with_punches_shows_its_row(self):
        self.punch(self.worker, datetime.date(2001, 3, 12))
        by_date = {d['date']: d for d in self.person()['days']}
        self.assertFalse(by_date['2001-03-09']['employed'])
        self.assertTrue(by_date['2001-03-10']['employed'])
        row = by_date['2001-03-12']['day']
        self.assertEqual((row['status'], row['worked_text'], row['overtime_text']), ('present', '9:30', '1:30'))
        self.assertIsNone(by_date['2001-03-13']['day'])                  # employed, nothing recorded

    def test_totals_match_the_month_sheet(self):
        self.punch(self.other, datetime.date(2001, 3, 1))
        self.punch(self.other, datetime.date(2001, 3, 2), came=(8, 0), left=(12, 30))      # half day
        services.set_day(self.other, datetime.date(2001, 3, 3), AttendanceDay.LEAVE, None)
        services.set_day(self.other, datetime.date(2001, 3, 4), AttendanceDay.WEEKLY_OFF, None)
        data = self.person(self.other)
        sheet = next(e for e in services.month_sheet(2001, 3) if e['worker'].pk == self.other.pk)
        self.assertEqual(data['counts'], sheet['counts'])
        self.assertEqual(data['paid_days'], sheet['paid_days'])
        self.assertEqual(data['paid_days'], 1 + 0.5 + 1 + 1)
        self.assertEqual(data['worked_text'], '14:00')                                       # 9:30 + 4:30
        self.assertEqual(data['overtime_text'], '1:30')

    def test_every_raw_punch_of_the_day_is_listed_in_order_double_taps_included(self):
        day = datetime.date(2001, 3, 12)
        services.record_punches([
            {'emp_code': '6601', 'punched_at': at(day, 8, 0), 'device': 'GATE-1', 'note': 'first'},
            {'emp_code': '6601', 'punched_at': at(day, 8, 1)},                       # a double tap
            {'emp_code': '6601', 'punched_at': at(day, 12, 30)},                     # out on a break
            {'emp_code': '6601', 'punched_at': at(day, 13, 0)},
            {'emp_code': '6601', 'punched_at': at(day, 17, 30)},
        ])
        by_date = {d['date']: d for d in self.person()['days']}
        punches = by_date['2001-03-12']['punches']
        self.assertEqual([p['punched_at'][11:16] for p in punches], ['08:00', '08:01', '12:30', '13:00', '17:30'])
        self.assertEqual((punches[0]['device'], punches[0]['note']), ('GATE-1', 'first'))
        self.assertEqual(by_date['2001-03-13']['punches'], [])
        # the day row itself still uses the first and last punch
        self.assertEqual((by_date['2001-03-12']['day']['in_time'][11:16], by_date['2001-03-12']['day']['out_time'][11:16]),
                         ('08:00', '17:30'))

    def test_a_night_shifts_morning_punch_is_filed_under_the_evening_it_started(self):
        evening = datetime.date(2001, 3, 15)
        services.record_punches([
            {'emp_code': '6601', 'punched_at': at(evening, 20, 0)},
            {'emp_code': '6601', 'punched_at': at(evening + datetime.timedelta(days=1), 5, 10)},
        ])
        by_date = {d['date']: d for d in self.person()['days']}
        self.assertEqual([p['punched_at'] for p in by_date['2001-03-15']['punches']],
                         ['2001-03-15T20:00:00', '2001-03-16T05:10:00'])
        self.assertEqual(by_date['2001-03-16']['punches'], [])

    def test_a_night_shift_that_started_last_month_is_not_listed_this_month(self):
        services.record_punches([
            {'emp_code': '6602', 'punched_at': at(datetime.date(2001, 2, 28), 20, 0)},
            {'emp_code': '6602', 'punched_at': at(datetime.date(2001, 3, 1), 5, 0)},
        ])
        days = self.person(self.other)['days']
        self.assertEqual(days[0]['punches'], [])                                         # 1 March: nothing started that day

    def test_company_holidays_are_named_on_their_day(self):
        Holiday.objects.create(date=datetime.date(2001, 3, 14), name='Holi')
        by_date = {d['date']: d for d in self.person(self.other)['days']}
        self.assertEqual(by_date['2001-03-14']['holiday'], 'Holi')
        self.assertEqual(by_date['2001-03-15']['holiday'], '')

    def test_not_marked_counts_employed_past_days_with_no_row(self):
        services.set_day(self.other, datetime.date(2001, 3, 1), AttendanceDay.LEAVE, None)
        self.assertEqual(self.person(self.other)['not_marked'], 30)      # 31 days, one has a row
        self.assertEqual(self.person(self.left)['not_marked'], 20)       # left on the 20th: only 1-20 count

    def test_a_worker_who_left_can_still_be_opened_for_a_past_month(self):
        self.punch(self.left, datetime.date(2001, 3, 5))
        data = self.person(self.left)
        self.assertEqual(data['counts'], {'present': 1})
        self.assertFalse({d['date']: d for d in data['days']}['2001-03-25']['employed'])

    def test_people_lists_active_workers_and_those_with_history(self):
        self.punch(self.left, datetime.date(2001, 3, 5))
        people = {p['name']: p for p in self.api.get(DAYS + 'people/').json()}
        self.assertTrue({'PM WORKER', 'PM OTHER', 'PM LEFT'} <= set(people))
        self.assertFalse(people['PM LEFT']['is_active'])
        self.assertEqual(people['PM WORKER']['emp_code'], '6601')

    def test_a_worker_who_left_with_no_history_is_not_listed(self):
        gone = Worker.objects.create(worker_name='PM GONE', emp_code='6604', is_active=False,
                                     date_of_join=datetime.date(2000, 1, 1))
        self.assertNotIn('PM GONE', {p['name'] for p in self.api.get(DAYS + 'people/').json()})
        self.assertEqual(gone.pk, Worker.objects.get(worker_name='PM GONE').pk)

    def test_bad_requests_are_refused_clearly(self):
        self.assertEqual(self.api.get(DAYS + 'person/', {'month': MARCH}).status_code, 400)               # no worker
        self.assertEqual(self.api.get(DAYS + 'person/', {'worker': 99999999, 'month': MARCH}).status_code, 400)
        self.assertEqual(self.api.get(DAYS + 'person/', {'worker': self.worker.pk}).status_code, 400)     # no month
        self.assertEqual(self.api.get(DAYS + 'person/', {'worker': self.worker.pk, 'month': '2001-13'}).status_code, 400)

    def test_only_staff_may_look(self):
        self.api.force_authenticate(self.plain)
        for url in ('person/?worker=1&month=2001-03', 'people/'):
            self.assertIn(self.api.get(DAYS + url).status_code, (403, 404))
