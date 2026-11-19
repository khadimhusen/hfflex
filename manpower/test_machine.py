"""Manpower uses itemmaster's Machine (it used to have its own copy)."""
import datetime

from django.contrib.auth.models import User
from django.test import Client, TestCase
from rest_framework.test import APIClient

from itemmaster.models import Machine
from manpower.models import Shift, TimeMaster

DAY = '2001-03-01'


def machine(name, user=None):
    return Machine.objects.create(
        machinename=name, max_speed=100, mode_speed=80, est_date=datetime.date(2020, 1, 1), user=user)


class MachineBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('mpstaff', 'a@example.com', 'x', is_staff=True)
        cls.operator = User.objects.create_user('MPTEST-OP', 'b@example.com', 'x')
        cls.other_user = User.objects.create_user('MPTEST-OTHER', 'c@example.com', 'x')
        cls.no_machine_user = User.objects.create_user('mpnomachine', 'd@example.com', 'x')
        cls.printer = machine('MPTEST PRINTING', user=cls.operator)          # has make-ready times
        cls.idle = machine('MPTEST IDLE', user=cls.other_user)               # a real machine, but no times set up
        for kind, minutes in (('Full', 60), ('Half', 30), ('Running', 10)):
            TimeMaster.objects.create(machine=cls.printer, makeready=kind, allotedtime=minutes)

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.staff)


class ShiftsUseTheItemmasterMachine(MachineBase):
    def test_a_shift_points_at_the_itemmaster_machine_and_shows_its_name(self):
        shift = Shift.objects.create(shift='Day', machine=self.printer, production_date=datetime.date(2001, 3, 1))
        self.assertIsInstance(shift.machine, Machine)
        self.assertEqual(str(shift), '2001-03-01 Day Shift- MPTEST PRINTING')
        data = self.api.get(f'/api/manpower/shifts/{shift.pk}/').json()
        self.assertEqual((data['machine'], data['machine_display']), (self.printer.pk, 'MPTEST PRINTING'))

    def test_the_old_manpower_machine_is_gone(self):
        from django.apps import apps
        with self.assertRaises(LookupError):
            apps.get_model('manpower', 'Machine')

    def test_filtering_shifts_by_machine_still_works(self):
        Shift.objects.create(shift='Day', machine=self.printer, production_date=datetime.date(2001, 3, 1))
        rows = self.api.get('/api/manpower/shifts/', {'machine': self.printer.pk}).json()['results']
        self.assertEqual([r['machine_display'] for r in rows], ['MPTEST PRINTING'])
        self.assertEqual(self.api.get('/api/manpower/shifts/', {'machine': self.idle.pk}).json()['results'], [])


class OnlyMachinesWithMakeReadyTimesRunShifts(MachineBase):
    def test_the_machine_lookup_lists_only_machines_with_times(self):
        names = [m['machinename'] for m in self.api.get('/api/manpower/machine-lookup/', {'page_size': 100}).json()['results']]
        self.assertIn('MPTEST PRINTING', names)
        self.assertNotIn('MPTEST IDLE', names)
        self.assertEqual(len(names), len(set(names)), 'a machine with three time rows must be listed once')

    def test_an_inactive_machine_is_not_offered(self):
        Machine.objects.filter(pk=self.printer.pk).update(active=False)
        names = [m['machinename'] for m in self.api.get('/api/manpower/machine-lookup/', {'page_size': 100}).json()['results']]
        self.assertNotIn('MPTEST PRINTING', names)

    def test_a_shift_can_be_created_on_a_machine_with_times(self):
        response = self.api.post('/api/manpower/shifts/', {'shift': 'Day', 'machine': self.printer.pk,
                                                           'production_date': DAY}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()['machine_display'], 'MPTEST PRINTING')

    def test_a_shift_cannot_be_created_on_a_machine_without_times(self):
        response = self.api.post('/api/manpower/shifts/', {'shift': 'Day', 'machine': self.idle.pk,
                                                           'production_date': DAY}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('make-ready times', response.content.decode())
        self.assertFalse(Shift.objects.filter(machine=self.idle).exists())


class NewShiftInTheOldApp(MachineBase):
    def post(self, user):
        client = Client()
        client.force_login(user)
        return client.post('/manpower/newshift/', {'shift': 'Day', 'production_date': '01/03/2001'})

    def test_a_machine_login_starts_a_shift_on_its_own_machine(self):
        response = self.post(self.operator)
        shift = Shift.objects.get(machine=self.printer, production_date=datetime.date(2001, 3, 1))
        self.assertRedirects(response, f'/manpower/shiftdetail/{shift.pk}/', fetch_redirect_response=False)
        self.assertEqual(shift.createdby, self.operator)

    def test_the_login_name_no_longer_has_to_equal_the_machine_name(self):
        self.assertNotEqual(self.operator.username, self.printer.machinename)
        self.post(self.operator)
        self.assertTrue(Shift.objects.filter(machine=self.printer).exists())

    def test_a_user_with_no_machine_is_refused(self):
        response = self.post(self.no_machine_user)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Shift.objects.filter(production_date=datetime.date(2001, 3, 1)).exists())

    def test_a_machine_login_whose_machine_has_no_times_is_refused(self):
        self.post(self.other_user)
        self.assertFalse(Shift.objects.filter(machine=self.idle).exists())
