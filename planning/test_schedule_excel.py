import datetime
from io import BytesIO
from unittest import mock

from django.test import Client
from django.urls import reverse
from openpyxl import load_workbook

from itemmaster.models import Machine
from planning.models import IdleTime, MachineSchedule
from planning.test_schedule_pdf import SchedulePdfBase

MIN = datetime.timedelta(minutes=1)
XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


class ScheduleExcelTests(SchedulePdfBase):
    def excel(self, machine):
        return self.web.get(reverse('planning:machine_schedule_excel', args=[machine.id]))

    def sheet(self, machine):
        response = self.excel(machine)
        self.assertEqual(response.status_code, 200)
        return load_workbook(BytesIO(response.content)).active

    @staticmethod
    def table(sheet):
        rows = list(sheet.iter_rows(min_row=4, values_only=True))
        headers = list(rows[0])
        return headers, [dict(zip(headers, row)) for row in rows[1:]]

    # ---- the download --------------------------------------------------
    def test_it_downloads_an_xlsx_named_for_the_machine(self):
        response = self.excel(self.printing)
        self.assertEqual(response['Content-Type'], XLSX)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertRegex(response['Content-Disposition'], r'schedule_PRINTING_PDF_2_\d{8}_\d{4}\.xlsx')
        self.assertTrue(response.content.startswith(b'PK'))          # an xlsx is a zip

    def test_unknown_machine_is_a_404(self):
        self.assertEqual(self.web.get(reverse('planning:machine_schedule_excel', args=[999999999])).status_code, 404)

    def test_same_access_as_the_pdf(self):
        url = reverse('planning:machine_schedule_excel', args=[self.printing.id])
        with mock.patch('planning.views.get_planning_role', return_value=None):
            self.assertEqual(self.web.get(url).status_code, 403)
        with mock.patch('planning.views.get_planning_role', return_value='viewer'):
            self.assertEqual(self.web.get(url).status_code, 200)
        with mock.patch('planning.views.get_planning_role', return_value='operator'), \
                mock.patch('planning.views.get_operator_machine', return_value=self.printing):
            self.assertEqual(self.web.get(url).status_code, 200)
            other = reverse('planning:machine_schedule_excel', args=[self.lamination.id])
            self.assertEqual(self.web.get(other).status_code, 403)

    def test_anonymous_is_sent_to_the_login(self):
        response = Client().get(reverse('planning:machine_schedule_excel', args=[self.printing.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response['Location'])

    # ---- the content ---------------------------------------------------
    def test_title_and_the_rows_in_schedule_order(self):
        sheet = self.sheet(self.lamination)
        self.assertEqual(sheet['A1'].value, 'Machine Schedule - LAMINATION-PDF')
        self.assertEqual(sheet.title, 'LAMINATION-PDF')
        headers, rows = self.table(sheet)
        self.assertNotIn('Cylinder', headers)
        self.assertEqual([r['Status'] for r in rows], ['Completed', 'Running', 'Pending'])
        self.assertEqual([r['#'] for r in rows], [None, None, 1])

    def test_a_printing_machine_has_the_cylinder_column_after_the_job(self):
        headers, rows = self.table(self.sheet(self.printing))
        self.assertEqual(headers[:3], ['#', 'Job / Reason', 'Cylinder'])
        expected = self.processes[0].job.itemmaster.cylinder_status or 'Not Available'
        self.assertEqual(rows[0]['Cylinder'], expected)

    def test_numbers_dates_and_durations_are_real_excel_values(self):
        sheet = self.sheet(self.lamination)
        headers, rows = self.table(sheet)
        done = rows[0]
        self.assertEqual(done['Qty'], 100)
        self.assertIsInstance(done['Qty'], (int, float))          # a number, not text
        self.assertEqual(done['Speed'], 10)
        self.assertEqual(done['Start'], datetime.datetime(2026, 10, 1, 8, 0))
        self.assertEqual(done['End'], datetime.datetime(2026, 10, 1, 9, 0))
        start_col = headers.index('Start') + 1
        est_col = headers.index('Est. Duration') + 1
        self.assertEqual(sheet.cell(row=5, column=start_col).number_format, 'dd/mm/yyyy hh:mm')
        self.assertEqual(sheet.cell(row=5, column=est_col).number_format, '[h]:mm')
        self.assertEqual(sheet.cell(row=5, column=est_col).value, 30 * MIN)

    def test_variance_is_signed_minutes(self):
        MachineSchedule.objects.filter(machine=self.lamination, queue_position=-1).update(time_variance=-10 * MIN)
        MachineSchedule.objects.filter(machine=self.lamination, queue_position=0).update(time_variance=95 * MIN)
        headers, rows = self.table(self.sheet(self.lamination))
        self.assertEqual([r['Variance (min)'] for r in rows], [-10, 95, None])

    def test_an_idle_slot_is_labelled_and_has_no_cylinder(self):
        reason = IdleTime.objects.create(name='TEST XL IDLE', category='Planned')
        MachineSchedule.objects.create(
            schedule_type='Idle', idle_reason=reason, idle_notes='lunch', machine=self.printing,
            status='Pending', queue_position=2, estimated_duration=30 * MIN)
        headers, rows = self.table(self.sheet(self.printing))
        idle = rows[-1]
        self.assertEqual((idle['Status'], idle['Job / Reason'], idle['Process']), ('Idle', 'IDLE - TEST XL IDLE', 'lunch'))
        self.assertIsNone(idle['Cylinder'])

    def test_an_empty_machine_still_opens(self):
        empty = Machine.objects.create(machinename='PRINTING-XL-EMPTY', max_speed=1, mode_speed=1,
                                       est_date=datetime.date.today())
        sheet = self.sheet(empty)
        self.assertEqual(sheet['B5'].value, 'No schedules')

    def test_a_machine_name_that_is_not_a_valid_sheet_title_is_cleaned(self):
        odd = Machine.objects.create(machinename='ODD/NAME:[1]*?', max_speed=1, mode_speed=1,
                                     est_date=datetime.date.today())
        self.assertEqual(self.sheet(odd).title, 'ODD-NAME--1---')

    def test_header_row_is_frozen_and_filterable(self):
        sheet = self.sheet(self.printing)
        self.assertEqual(sheet.freeze_panes, 'C5')
        self.assertTrue(sheet.auto_filter.ref.startswith('A4:'))
