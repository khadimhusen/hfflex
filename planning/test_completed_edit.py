import datetime
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from itemmaster.models import Machine, MachineTask
from order.models import JobProcess
from planning.models import IdleTime, MachineDowntime, MachineSchedule, ProductionTask

MIN = datetime.timedelta(minutes=1)


class CompletedEditBase(TestCase):
    """One completed production row: 600 qty at speed 10 -> 60 min running, one
    makeready task (10 min at 2 persons) -> estimated 70 min; it ran 3 h, so
    the variance is +110 min."""

    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_superuser('cedstaff', 's@example.com', 'x')
        # A manager by role (superuser) who is NOT a staff user.
        cls.manager = User.objects.create_superuser('cedmgr', 'm@example.com', 'x')
        User.objects.filter(pk=cls.manager.pk).update(is_staff=False)
        cls.manager.refresh_from_db()

        today = datetime.date.today()
        cls.machine = Machine.objects.create(machinename='TEST CED-1', max_speed=1, mode_speed=1, est_date=today)
        cls.other = Machine.objects.create(machinename='TEST CED-2', max_speed=1, mode_speed=1, est_date=today)
        cls.makeready = MachineTask.objects.create(
            machine=cls.machine, category='Makeready', persons_required=2, task='TEST CED TASK', duration=10)

        cls.start = datetime.datetime(2026, 10, 1, 8, 0)
        cls.end = cls.start + datetime.timedelta(hours=3)
        cls.job_process = JobProcess.objects.first()
        cls.row = MachineSchedule.objects.create(
            schedule_type='Production', jobprocess=cls.job_process, machine=cls.machine, qty=600, speed=10,
            persons_assigned=2, status='Completed', queue_position=-1, start_time=cls.start, end_time=cls.end,
            makeready_duration=10 * MIN, running_duration=60 * MIN, downtime_duration=datetime.timedelta(0),
            estimated_duration=70 * MIN, time_variance=110 * MIN, remark='first remark',
            raw_material_status='Available',
        )
        ProductionTask.objects.create(machine_schedule=cls.row, task=cls.makeready, qty=1, time_per_task=10)
        MachineSchedule.objects.filter(pk=cls.row.pk).update(
            makeready_duration=10 * MIN, estimated_duration=70 * MIN, time_variance=110 * MIN)

        cls.reason = IdleTime.objects.create(name='TEST CED IDLE', category='Planned')
        cls.unplanned = IdleTime.objects.create(name='TEST CED BREAKDOWN', category='Unplanned')
        cls.idle_row = MachineSchedule.objects.create(
            schedule_type='Idle', idle_reason=cls.reason, machine=cls.machine, status='Completed',
            queue_position=-1, start_time=cls.start - datetime.timedelta(hours=2),
            end_time=cls.start - datetime.timedelta(hours=1), estimated_duration=30 * MIN,
            time_variance=30 * MIN,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.staff)

    def fresh(self, row=None):
        return MachineSchedule.objects.get(pk=(row or self.row).pk)

    def url(self, name, row=None):
        return f'/api/planning/machine-schedules/{(row or self.row).pk}/{name}/'

    def edit(self, row=None, **payload):
        return self.client.post(self.url('edit-completed', row), payload, format='json')

    def as_user(self, user):
        self.client.force_authenticate(user)


class EditCompletedTests(CompletedEditBase):
    def test_staff_can_correct_the_actual_times_and_the_variance_follows(self):
        response = self.edit(start_time='2026-10-01T08:00', end_time='2026-10-01T10:00')
        self.assertEqual(response.status_code, 200, response.content)
        row = self.fresh()
        self.assertEqual(row.end_time, datetime.datetime(2026, 10, 1, 10, 0))
        self.assertEqual(row.time_variance, 50 * MIN)          # 120 actual - 70 estimated
        self.assertEqual(row.editedby, self.staff)

    def test_a_manager_who_is_not_staff_cannot_edit(self):
        self.as_user(self.manager)
        self.assertEqual(self.edit(remark='nope').status_code, 404)   # PermissionDenied is shown as 404
        self.assertEqual(self.fresh().remark, 'first remark')

    def test_anonymous_cannot_edit(self):
        self.client.force_authenticate(None)
        self.assertIn(self.edit(remark='nope').status_code, (401, 403))

    def test_staff_operator_only_on_their_own_machine(self):
        with mock.patch('planning.permissions.get_planning_role', return_value='operator'), \
                mock.patch('planning.utils.get_planning_role', return_value='operator'), \
                mock.patch('planning.utils.get_operator_machine', return_value=self.other):
            self.assertEqual(self.edit(remark='nope').status_code, 404)
        with mock.patch('planning.permissions.get_planning_role', return_value='operator'), \
                mock.patch('planning.utils.get_planning_role', return_value='operator'), \
                mock.patch('planning.utils.get_operator_machine', return_value=self.machine):
            self.assertEqual(self.edit(remark='mine').status_code, 200)

    def test_end_before_start_is_refused_and_nothing_changes(self):
        response = self.edit(start_time='2026-10-01T12:00', end_time='2026-10-01T10:00')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.fresh().end_time, self.end)

    def test_moving_only_the_start_past_the_existing_end_is_refused(self):
        self.assertEqual(self.edit(start_time='2026-10-01T23:00').status_code, 400)

    def test_a_bad_date_or_number_is_a_400(self):
        self.assertEqual(self.edit(start_time='not a date').status_code, 400)
        self.assertEqual(self.edit(speed='fast').status_code, 400)
        self.assertEqual(self.edit(speed=0).status_code, 400)
        self.assertEqual(self.edit(persons_assigned=0).status_code, 400)

    def test_speed_recomputes_running_estimate_and_variance(self):
        response = self.edit(speed=20)                      # 600 / 20 = 30 min running
        self.assertEqual(response.status_code, 200, response.content)
        row = self.fresh()
        self.assertEqual(row.speed, 20)
        self.assertEqual(row.running_duration, 30 * MIN)
        self.assertEqual(row.estimated_duration, 40 * MIN)  # 10 makeready + 30 running
        self.assertEqual(row.time_variance, 140 * MIN)      # 180 actual - 40

    def test_persons_recompute_makeready_from_the_tasks(self):
        # task: 10 min x 2 persons required x qty 1 / persons assigned
        response = self.edit(persons_assigned=4)
        self.assertEqual(response.status_code, 200, response.content)
        row = self.fresh()
        self.assertEqual(row.persons_assigned, 4)
        self.assertEqual(row.makeready_duration, 5 * MIN)
        self.assertEqual(row.estimated_duration, 65 * MIN)
        self.assertEqual(row.time_variance, 115 * MIN)

    def test_remark_and_material_status(self):
        response = self.edit(remark='corrected', material_status='Not Available')
        self.assertEqual(response.status_code, 200, response.content)
        row = self.fresh()
        self.assertEqual((row.remark, row.raw_material_status), ('corrected', 'Not Available'))
        self.assertEqual(self.edit(material_status='Whatever').status_code, 400)

    def test_remark_can_be_cleared(self):
        self.assertEqual(self.edit(remark='').status_code, 200)
        self.assertEqual(self.fresh().remark, '')

    def test_an_omitted_field_is_left_alone(self):
        self.edit(remark='only this')
        row = self.fresh()
        self.assertEqual((row.speed, row.persons_assigned, row.end_time), (10, 2, self.end))

    def test_an_idle_row_takes_only_times(self):
        response = self.edit(self.idle_row, end_time='2026-10-01T06:30', speed=99, remark='ignored')
        self.assertEqual(response.status_code, 200, response.content)
        row = self.fresh(self.idle_row)
        self.assertEqual(row.end_time, datetime.datetime(2026, 10, 1, 6, 30))
        self.assertIsNone(row.speed)
        self.assertIsNone(row.remark)

    def test_only_completed_rows_can_be_edited_here(self):
        MachineSchedule.objects.filter(pk=self.idle_row.pk).update(queue_position=0, status='Running')
        self.assertEqual(self.edit(self.idle_row, remark='x').status_code, 404)

    def test_the_board_tells_the_page_whether_editing_is_allowed(self):
        url = reverse('planning-machine-board', args=[self.machine.id])
        self.assertTrue(self.client.get(url).json()['can_edit_completed'])
        self.as_user(self.manager)
        self.assertFalse(self.client.get(url).json()['can_edit_completed'])

    def test_with_nothing_running_the_newest_end_time_moves_the_queued_jobs(self):
        queued_process = JobProcess.objects.exclude(pk=self.job_process.pk).first()
        queued = MachineSchedule.objects.create(
            schedule_type='Production', jobprocess=queued_process, machine=self.machine, qty=100, speed=10,
            persons_assigned=2, status='Pending', queue_position=1, estimated_duration=30 * MIN,
            running_duration=10 * MIN, makeready_duration=20 * MIN,
        )
        self.assertEqual(self.edit(end_time='2026-10-01T12:00').status_code, 200)
        queued.refresh_from_db()
        self.assertEqual(queued.start_time, datetime.datetime(2026, 10, 1, 12, 0))


class CompletedTasksAndDowntimeTests(CompletedEditBase):
    def test_staff_can_change_the_tasks_of_a_completed_row(self):
        task = self.row.productiontasks.get()
        response = self.client.post(self.url('tasks'), {'tasks': [
            {'id': task.pk, 'qty': 2, 'time_per_task': 10}]}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        row = self.fresh()
        # 2 x 10 = 20 min makeready (+ the 60 running) -> estimated 80, variance 100
        self.assertEqual(row.estimated_duration, 80 * MIN)
        self.assertEqual(row.time_variance, 100 * MIN)

    def test_a_manager_who_is_not_staff_cannot_change_completed_tasks(self):
        task = self.row.productiontasks.get()
        self.as_user(self.manager)
        response = self.client.post(self.url('tasks'), {'tasks': [
            {'id': task.pk, 'qty': 9, 'time_per_task': 9}]}, format='json')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.row.productiontasks.get().qty, 1)

    def test_completed_tasks_can_still_be_read_by_a_manager(self):
        self.as_user(self.manager)
        self.assertEqual(self.client.get(self.url('tasks')).status_code, 200)

    def test_staff_can_add_edit_and_delete_downtime_on_a_completed_row(self):
        response = self.client.post(self.url('downtime'), {
            'action': 'add', 'reason_id': self.unplanned.pk, 'hours': 0, 'mins': 20, 'notes': 'belt'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        row = self.fresh()
        self.assertEqual(row.downtime_duration, 20 * MIN)
        self.assertEqual(row.estimated_duration, 90 * MIN)
        self.assertEqual(row.time_variance, 90 * MIN)

        downtime = MachineDowntime.objects.get(machine_schedule=self.row)
        self.client.post(self.url('downtime'), {
            'action': 'edit', 'downtime_id': downtime.pk, 'reason_id': self.unplanned.pk,
            'hours': 0, 'mins': 40, 'notes': 'belt'}, format='json')
        self.assertEqual(self.fresh().time_variance, 70 * MIN)

        self.client.post(self.url('downtime'), {'action': 'delete', 'downtime_id': downtime.pk}, format='json')
        row = self.fresh()
        self.assertEqual(row.downtime_duration, datetime.timedelta(0))
        self.assertEqual(row.time_variance, 110 * MIN)

    def test_a_manager_who_is_not_staff_cannot_add_downtime_to_a_completed_row(self):
        self.as_user(self.manager)
        response = self.client.post(self.url('downtime'), {
            'action': 'add', 'reason_id': self.unplanned.pk, 'hours': 1, 'mins': 0}, format='json')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(MachineDowntime.objects.filter(machine_schedule=self.row).count(), 0)

    def test_completed_downtime_can_still_be_listed(self):
        self.as_user(self.manager)
        self.assertEqual(self.client.get(self.url('downtime')).status_code, 200)


class OldDjangoViewTests(CompletedEditBase):
    """The legacy page's JSON views (planning/views.py)."""

    def setUp(self):
        from django.test import Client
        self.web = Client()
        self.web.force_login(self.staff)

    def post(self, name, row=None, machine=None, **payload):
        import json
        url = reverse(f'planning:{name}', args=[(machine or self.machine).id, (row or self.row).pk])
        return self.web.post(url, json.dumps(payload), content_type='application/json')

    def get(self, name, row=None):
        return self.web.get(reverse(f'planning:{name}', args=[self.machine.id, (row or self.row).pk]))

    def login_as(self, user):
        self.web.force_login(user)

    def test_staff_can_edit_a_completed_row(self):
        response = self.post('edit_completed', start_time='2026-10-01T08:00:00', end_time='2026-10-01T10:00:00',
                             speed=20, persons_assigned=4, remark='fixed', material_status='Not Available')
        self.assertEqual(response.status_code, 200, response.content)
        row = self.fresh()
        self.assertEqual(row.end_time, datetime.datetime(2026, 10, 1, 10, 0))
        # 5 makeready (4 persons) + 30 running = 35 estimated; 120 actual
        self.assertEqual(row.estimated_duration, 35 * MIN)
        self.assertEqual(row.time_variance, 85 * MIN)
        self.assertEqual((row.remark, row.raw_material_status, row.editedby), ('fixed', 'Not Available', self.staff))

    def test_a_manager_who_is_not_staff_is_refused(self):
        self.login_as(self.manager)
        response = self.post('edit_completed', remark='nope')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.fresh().remark, 'first remark')

    def test_bad_input_is_a_400_with_a_message(self):
        for payload in ({'end_time': '2026-10-01T06:00:00'}, {'end_time': 'garbage'}, {'speed': 'x'},
                        {'speed': 0}, {'material_status': 'Whatever'}):
            response = self.post('edit_completed', **payload)
            self.assertEqual(response.status_code, 400, payload)
            self.assertTrue(response.json()['message'], payload)
        self.assertEqual(self.fresh().end_time, self.end)

    def test_it_only_accepts_post_and_only_completed_rows(self):
        self.assertEqual(self.get('edit_completed').status_code, 405)
        MachineSchedule.objects.filter(pk=self.idle_row.pk).update(queue_position=0, status='Running')
        self.assertEqual(self.post('edit_completed', row=self.idle_row, remark='x').status_code, 404)

    def test_a_row_of_another_machine_is_not_found(self):
        self.assertEqual(self.post('edit_completed', machine=self.other, remark='x').status_code, 404)

    def test_completed_tasks_are_staff_only_and_update_the_variance(self):
        task = self.row.productiontasks.get()
        self.login_as(self.manager)
        self.assertEqual(self.get('schedule_tasks').status_code, 403)
        self.assertEqual(self.post('schedule_tasks', tasks=[{'id': task.pk, 'qty': 9, 'time_per_task': 9}]).status_code, 403)
        self.login_as(self.staff)
        self.assertEqual(self.get('schedule_tasks').status_code, 200)
        response = self.post('schedule_tasks', tasks=[{'id': task.pk, 'qty': 2, 'time_per_task': 10}])
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.fresh().time_variance, 100 * MIN)

    def test_completed_downtime_changes_are_staff_only(self):
        add = dict(action='add', reason_id=self.unplanned.pk, hours=0, mins=20, notes='belt')
        self.login_as(self.manager)
        self.assertEqual(self.get('add_downtime').status_code, 200)            # reading is fine
        self.assertEqual(self.post('add_downtime', **add).status_code, 403)
        self.login_as(self.staff)
        self.assertEqual(self.post('add_downtime', **add).status_code, 200)
        row = self.fresh()
        self.assertEqual((row.downtime_duration, row.time_variance), (20 * MIN, 90 * MIN))

    def test_a_manager_still_reaches_the_tasks_of_a_queued_row(self):
        queued_process = JobProcess.objects.exclude(pk=self.job_process.pk).first()
        queued = MachineSchedule.objects.create(
            schedule_type='Production', jobprocess=queued_process, machine=self.machine, qty=100, speed=10,
            persons_assigned=2, status='Pending', queue_position=1, estimated_duration=30 * MIN,
        )
        self.login_as(self.manager)
        self.assertEqual(self.get('schedule_tasks', row=queued).status_code, 200)

    def test_the_page_shows_the_edit_controls_only_to_staff(self):
        url = reverse('planning:machine_schedule', args=[self.machine.id])
        html = self.web.get(url).content.decode()
        self.assertIn('openEditCompletedModal', html)
        self.assertIn('id="editCompletedModal"', html)
        self.assertIn('function confirmEditCompleted', html)
        self.assertIn('id="tasksModal"', html)
        self.login_as(self.manager)
        html = self.web.get(url).content.decode()
        self.assertNotIn('openEditCompletedModal', html)
        self.assertNotIn('editCompletedModal', html)
        self.assertIn('id="tasksModal"', html)          # managers keep the tasks dialog for queued rows
