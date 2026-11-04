import datetime
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from itemmaster.models import Machine
from planning.api_viewsets import BOARD_COMPLETED_SHOWN
from planning.models import IdleTime, MachineSchedule


class CompletedHistoryTests(TestCase):
    TOTAL = 23

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('histmgr', 'h@example.com', 'x')
        today = datetime.date.today()
        cls.machine = Machine.objects.create(machinename='TEST HIST-1', max_speed=1, mode_speed=1, est_date=today)
        cls.other = Machine.objects.create(machinename='TEST HIST-2', max_speed=1, mode_speed=1, est_date=today)
        cls.reason = IdleTime.objects.create(name='TEST HIST REASON')
        base = timezone.now() - datetime.timedelta(days=60)
        rows = []
        for i in range(cls.TOTAL):
            # Rows 10 and 11 finish at the same instant: ties must page consistently.
            end = base + datetime.timedelta(hours=i if i != 11 else 10)
            rows.append(MachineSchedule(
                schedule_type='Idle', idle_reason=cls.reason, machine=cls.machine, queue_position=-1,
                status='Completed', start_time=end - datetime.timedelta(minutes=30), end_time=end,
                estimated_duration=datetime.timedelta(minutes=30), idle_notes=f'row {i}',
            ))
        MachineSchedule.objects.bulk_create(rows)

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def board(self, machine=None):
        url = reverse('planning-machine-board', args=[(machine or self.machine).id])
        return self.client.get(url).json()

    def history(self, offset=None, limit=None, machine=None):
        params = {k: v for k, v in (('offset', offset), ('limit', limit)) if v is not None}
        url = reverse('planning-completed-history', args=[(machine or self.machine).id])
        return self.client.get(url, params)

    def test_board_shows_the_newest_rows_oldest_first(self):
        board = self.board()
        self.assertEqual(len(board['completed']), BOARD_COMPLETED_SHOWN)
        self.assertEqual(board['completed_count'], self.TOTAL)
        notes = [r['idle_notes'] for r in board['completed']]
        self.assertEqual(notes[-1], f'row {self.TOTAL - 1}')

    def test_first_page_starts_just_behind_the_board(self):
        body = self.history().json()
        self.assertEqual(len(body['results']), 10)
        self.assertEqual(body['count'], self.TOTAL)
        self.assertTrue(body['has_more'])
        # oldest first inside the page, and entirely older than the board's rows
        ends = [r['end_time'] for r in body['results']]
        self.assertEqual(ends, sorted(ends))
        board_first_end = self.board()['completed'][0]['end_time']
        self.assertLessEqual(ends[-1], board_first_end)

    def test_paging_through_everything_gives_each_row_exactly_once(self):
        seen = [r['id'] for r in self.board()['completed']]
        offset = len(seen)
        while True:
            body = self.history(offset=offset, limit=7).json()
            seen.extend(r['id'] for r in body['results'])
            offset += 7
            if not body['has_more']:
                break
        self.assertEqual(len(seen), self.TOTAL)
        self.assertEqual(len(set(seen)), self.TOTAL)

    def test_last_page_says_there_is_no_more(self):
        body = self.history(offset=20, limit=10).json()
        self.assertEqual(len(body['results']), 3)
        self.assertFalse(body['has_more'])

    def test_offset_past_the_end_is_empty_not_an_error(self):
        body = self.history(offset=500).json()
        self.assertEqual(body['results'], [])
        self.assertFalse(body['has_more'])

    def test_limit_is_capped(self):
        self.assertEqual(len(self.history(offset=0, limit=9999).json()['results']), self.TOTAL)

    def test_only_this_machines_rows_come_back(self):
        self.assertEqual(self.history(machine=self.other).json()['count'], 0)

    def test_bad_numbers_are_a_400(self):
        self.assertEqual(self.history(offset='abc').status_code, 400)
        self.assertEqual(self.history(limit='x').status_code, 400)

    def test_unknown_machine_is_a_404(self):
        url = reverse('planning-completed-history', args=[999999999])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_anonymous_is_refused(self):
        anon = APIClient()
        url = reverse('planning-completed-history', args=[self.machine.id])
        self.assertIn(anon.get(url).status_code, (401, 403))

    def test_an_operator_cannot_read_another_machines_history(self):
        with mock.patch('planning.permissions.get_planning_role', return_value='operator'), \
                mock.patch('planning.api_viewsets.get_planning_role', return_value='operator'), \
                mock.patch('planning.api_viewsets.get_operator_machine', return_value=self.other):
            # crm_exception_handler turns every PermissionDenied into a 404.
            self.assertEqual(self.history(machine=self.machine).status_code, 404)
            self.assertEqual(self.history(machine=self.other).status_code, 200)
