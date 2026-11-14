import datetime
from unittest import mock

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm

from itemmaster.models import Machine
from order.models import JobProcess
from planning.models import MachineSchedule
from planning.pdfs import columns, machine_table

MIN = datetime.timedelta(minutes=1)
CELL = ParagraphStyle('cell', fontSize=7)


class SchedulePdfBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('pdfuser', 'p@example.com', 'x')
        today = datetime.date.today()
        cls.printing = Machine.objects.create(machinename='PRINTING-PDF 2', max_speed=1, mode_speed=1, est_date=today)
        cls.lamination = Machine.objects.create(machinename='LAMINATION-PDF', max_speed=1, mode_speed=1, est_date=today)
        processes = list(JobProcess.objects.select_related('job__itemmaster')[:3])
        cls.processes = processes
        for machine in (cls.printing, cls.lamination):
            MachineSchedule.objects.create(
                schedule_type='Production', jobprocess=processes[0], machine=machine, qty=100, speed=10,
                status='Completed', queue_position=-1, start_time=datetime.datetime(2026, 10, 1, 8, 0),
                end_time=datetime.datetime(2026, 10, 1, 9, 0), estimated_duration=30 * MIN)
            MachineSchedule.objects.create(
                schedule_type='Production', jobprocess=processes[1], machine=machine, qty=100, speed=10,
                status='Running', queue_position=0, start_time=datetime.datetime(2026, 10, 1, 9, 0),
                estimated_duration=30 * MIN)
            MachineSchedule.objects.create(
                schedule_type='Production', jobprocess=processes[2], machine=machine, qty=100, speed=10,
                status='Pending', queue_position=1, estimated_duration=30 * MIN)

    def setUp(self):
        self.web = Client()
        self.web.force_login(self.user)

    def pdf(self, machine):
        return self.web.get(reverse('planning:machine_schedule_pdf', args=[machine.id]))


class MachinePdfViewTests(SchedulePdfBase):
    def test_a_manager_gets_a_pdf_for_one_machine(self):
        response = self.pdf(self.printing)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn('inline', response['Content-Disposition'])
        self.assertIn('schedule_PRINTING_PDF_2_', response['Content-Disposition'])

    def test_one_machine_is_smaller_than_all_machines(self):
        one = len(self.pdf(self.lamination).content)
        everything = len(self.web.get(reverse('planning:schedule_pdf')).content)
        self.assertLess(one, everything)

    def test_unknown_machine_is_a_404(self):
        self.assertEqual(self.web.get(reverse('planning:machine_schedule_pdf', args=[999999999])).status_code, 404)

    def test_a_user_with_no_planning_role_is_refused(self):
        with mock.patch('planning.views.get_planning_role', return_value=None):
            self.assertEqual(self.pdf(self.printing).status_code, 403)

    def test_a_viewer_can_print(self):
        with mock.patch('planning.views.get_planning_role', return_value='viewer'):
            self.assertEqual(self.pdf(self.printing).status_code, 200)

    def test_an_operator_can_print_only_their_own_machine(self):
        with mock.patch('planning.views.get_planning_role', return_value='operator'), \
                mock.patch('planning.views.get_operator_machine', return_value=self.printing):
            self.assertEqual(self.pdf(self.printing).status_code, 200)
            self.assertEqual(self.pdf(self.lamination).status_code, 403)

    def test_the_all_machines_pdf_stays_manager_or_supervisor_only(self):
        url = reverse('planning:schedule_pdf')
        with mock.patch('planning.views.get_planning_role', return_value='operator'):
            self.assertEqual(self.web.get(url).status_code, 403)
        with mock.patch('planning.views.get_planning_role', return_value='supervisor'):
            self.assertEqual(self.web.get(url).status_code, 200)

    def test_anonymous_is_sent_to_the_login(self):
        response = Client().get(reverse('planning:machine_schedule_pdf', args=[self.printing.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])


class MachineTableTests(SchedulePdfBase):
    def table(self, machine):
        return machine_table(machine, CELL)

    def test_a_printing_machine_gets_the_cylinder_column(self):
        data, widths, *_ = self.table(self.printing)
        self.assertEqual(data[0][2], 'Cylinder')
        cell = data[1][2].text
        self.assertEqual(cell, self.processes[0].job.itemmaster.cylinder_status or 'Not Available')

    def test_other_machines_do_not(self):
        data, widths, *_ = self.table(self.lamination)
        self.assertNotIn('Cylinder', data[0])

    def test_every_row_has_as_many_cells_as_headers_and_the_table_fits_the_page(self):
        for machine in (self.printing, self.lamination):
            data, widths, *_ = self.table(machine)
            self.assertTrue(all(len(row) == len(data[0]) == len(widths) for row in data), machine)
            self.assertLessEqual(sum(widths), 277 * mm, machine)

    def test_columns_helper_agrees(self):
        headers, widths = columns(True)
        self.assertEqual((len(headers), len(widths)), (15, 15))
        self.assertEqual(len(columns(False)[0]), 14)

    def test_row_order_and_plain_ascii_markers(self):
        data, widths, completed, running, hold = self.table(self.lamination)
        markers = [row[0] for row in data[1:]]
        self.assertEqual(markers, ['-', '>', '1'])
        self.assertTrue(all(m.isascii() for m in markers))
        self.assertEqual((completed, running, hold), ([1], 2, []))

    def test_an_empty_machine_still_makes_a_valid_table(self):
        empty = Machine.objects.create(machinename='PRINTING-EMPTY', max_speed=1, mode_speed=1,
                                       est_date=datetime.date.today())
        data, widths, completed, running, hold = self.table(empty)
        self.assertEqual(len(data), 2)
        self.assertEqual(len(data[1]), len(data[0]))
        self.assertEqual((completed, running, hold), ([], None, []))
