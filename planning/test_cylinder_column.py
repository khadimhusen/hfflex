import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from itemmaster.models import Machine
from order.models import JobProcess
from planning.models import IdleTime, MachineSchedule

MIN = datetime.timedelta(minutes=1)


class CylinderColumnTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('cylcol', 'c@example.com', 'x')
        today = datetime.date.today()
        cls.printing = Machine.objects.create(machinename='PRINTING-TEST', max_speed=1, mode_speed=1, est_date=today)
        cls.lamination = Machine.objects.create(machinename='LAMINATION-TEST', max_speed=1, mode_speed=1, est_date=today)
        cls.job_process = JobProcess.objects.select_related('job__itemmaster').first()
        cls.expected = cls.job_process.job.itemmaster.cylinder_status
        cls.production = MachineSchedule.objects.create(
            schedule_type='Production', jobprocess=cls.job_process, machine=cls.printing, qty=100, speed=10,
            persons_assigned=2, status='Pending', queue_position=1, estimated_duration=30 * MIN)
        reason = IdleTime.objects.create(name='TEST CYL IDLE', category='Planned')
        cls.idle = MachineSchedule.objects.create(
            schedule_type='Idle', idle_reason=reason, machine=cls.printing, status='Pending',
            queue_position=2, estimated_duration=30 * MIN)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def board(self, machine):
        return self.client.get(reverse('planning-machine-board', args=[machine.id])).json()

    def test_printing_machines_ask_for_the_cylinder_column(self):
        self.assertTrue(self.board(self.printing)['show_cylinder'])
        self.assertFalse(self.board(self.lamination)['show_cylinder'])

    def test_the_name_check_ignores_case(self):
        Machine.objects.filter(pk=self.lamination.pk).update(machinename='Printing-2')
        self.assertTrue(self.board(self.lamination)['show_cylinder'])

    def test_rows_carry_the_items_cylinder_status(self):
        queue = {row['id']: row for row in self.board(self.printing)['queue']}
        self.assertEqual(queue[self.production.pk]['cylinder_status'], self.expected)
        self.assertIsNone(queue[self.idle.pk]['cylinder_status'])
