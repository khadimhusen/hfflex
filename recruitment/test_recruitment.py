import datetime
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework.test import APIClient

from recruitment.models import Candidate, FeedbackRating, Interview, JobOpening

OPENINGS = '/api/recruitment/openings/'
CANDIDATES = '/api/recruitment/candidates/'
INTERVIEWS = '/api/recruitment/interviews/'
SUMMARY = '/api/recruitment/summary/'


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        def user(name, **extra):
            return User.objects.create_user(name, f'{name}@example.com', 'x', first_name=name.title(), **extra)
        cls.hr = user('rchr', is_staff=True)
        cls.panel1 = user('rcpanel1')
        cls.panel2 = user('rcpanel2')
        cls.stranger = user('rcstranger')

    def setUp(self):
        self.api = APIClient()
        self.as_user(self.hr)

    def as_user(self, user):
        self.api.force_authenticate(user)

    def make_opening(self, **extra):
        data = {
            'title': 'Production Manager', 'department': 'Production', 'positions': 1,
            'criteria': [{'name': 'Process knowledge', 'weight': 5}, {'name': 'Planning', 'weight': 3}],
        }
        data.update(extra)
        response = self.api.post(OPENINGS, data, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def make_candidate(self, opening, **extra):
        data = {'opening': opening['id'], 'name': 'Ramesh Patel', 'mobile': '98250 11111'}
        data.update(extra)
        response = self.api.post(CANDIDATES, data, format='multipart')
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def schedule(self, candidate, panel=None, **extra):
        data = {
            'candidate': candidate['id'], 'round_type': 'Technical', 'scheduled_at': '2026-12-01T11:00:00',
            'panel_ids': [u.pk for u in (panel or [self.panel1, self.panel2])],
        }
        data.update(extra)
        response = self.api.post(INTERVIEWS, data, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def ratings(self, opening, *values):
        return [{'criterion': c['id'], 'rating': v} for c, v in zip(opening['criteria'], values)]


class OpeningTests(Base):
    def test_number_is_allocated_per_year(self):
        first = self.make_opening(opened_date='2031-02-01')
        second = self.make_opening(opened_date='2031-03-01')
        self.assertEqual(first['number'], 'REQ-2031-001')
        self.assertEqual(second['number'], 'REQ-2031-002')

    def test_criteria_are_saved_in_order(self):
        opening = self.make_opening()
        self.assertEqual([c['name'] for c in opening['criteria']], ['Process knowledge', 'Planning'])

    def test_template_list_has_the_production_manager_scorecard(self):
        response = self.api.get(OPENINGS + 'criteria-templates/')
        self.assertEqual(response.status_code, 200)
        keys = {t['key']: t for t in response.json()}
        self.assertIn('production_manager', keys)
        self.assertGreaterEqual(len(keys['production_manager']['criteria']), 6)

    def test_max_below_min_is_rejected(self):
        response = self.api.post(OPENINGS, {'title': 'X', 'salary_min': 50000, 'salary_max': 40000}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_closing_sets_the_closed_date(self):
        opening = self.make_opening()
        response = self.api.patch(f'{OPENINGS}{opening["id"]}/', {'status': 'closed'}, format='json')
        self.assertEqual(response.json()['closed_date'], timezone.now().date().isoformat())

    def test_a_criterion_with_ratings_cannot_be_removed(self):
        opening = self.make_opening()
        candidate = self.make_candidate(opening)
        interview = self.schedule(candidate, panel=[self.panel1])
        self.as_user(self.panel1)
        response = self.api.post(f'{INTERVIEWS}{interview["id"]}/feedback/', {
            'recommendation': 'yes', 'ratings': self.ratings(opening, 4, 3)}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.as_user(self.hr)
        response = self.api.patch(f'{OPENINGS}{opening["id"]}/', {'criteria': [opening['criteria'][0]]},
                                  format='json')
        self.assertEqual(response.status_code, 400)

    def test_opening_with_candidates_cannot_be_deleted(self):
        opening = self.make_opening()
        self.make_candidate(opening)
        self.assertEqual(self.api.delete(f'{OPENINGS}{opening["id"]}/').status_code, 400)
        empty = self.make_opening(title='Other')
        self.assertEqual(self.api.delete(f'{OPENINGS}{empty["id"]}/').status_code, 204)

    def test_only_hr_can_use_openings(self):
        self.as_user(self.panel1)
        self.assertEqual(self.api.get(OPENINGS).status_code, 404)
        self.assertEqual(self.api.post(OPENINGS, {'title': 'X'}, format='json').status_code, 404)


class CandidateTests(Base):
    def test_new_candidate_starts_applied_with_a_log_line(self):
        candidate = self.make_candidate(self.make_opening())
        self.assertEqual(candidate['stage'], 'applied')
        self.assertEqual([l['to_stage'] for l in candidate['stage_logs']], ['applied'])

    def test_stage_cannot_be_patched_directly(self):
        candidate = self.make_candidate(self.make_opening())
        self.api.patch(f'{CANDIDATES}{candidate["id"]}/', {'stage': 'joined'}, format='json')
        self.assertEqual(Candidate.objects.get(pk=candidate['id']).stage, 'applied')

    def test_same_mobile_on_the_same_opening_is_a_duplicate(self):
        opening = self.make_opening()
        self.make_candidate(opening)
        response = self.api.post(CANDIDATES, {'opening': opening['id'], 'name': 'Someone', 'mobile': '+91 9825011111'},
                                 format='multipart')
        self.assertEqual(response.status_code, 400)
        other = self.make_opening(title='Quality Manager')
        self.make_candidate(other)           # a different opening is fine

    def test_move_to_rejected_needs_a_reason(self):
        candidate = self.make_candidate(self.make_opening())
        url = f'{CANDIDATES}{candidate["id"]}/move/'
        self.assertEqual(self.api.post(url, {'stage': 'rejected'}, format='json').status_code, 400)
        response = self.api.post(url, {'stage': 'rejected', 'rejection_reason': 'Not enough lamination exposure'},
                                 format='json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['stage'], 'rejected')
        self.assertEqual(response.json()['stage_logs'][-1]['to_stage'], 'rejected')

    def test_rejected_candidate_can_be_reopened_and_the_reason_clears(self):
        candidate = self.make_candidate(self.make_opening())
        url = f'{CANDIDATES}{candidate["id"]}/move/'
        self.api.post(url, {'stage': 'rejected', 'rejection_reason': 'Salary'}, format='json')
        response = self.api.post(url, {'stage': 'shortlisted'}, format='json')
        self.assertEqual(response.json()['rejection_reason'], '')

    def test_joined_needs_a_selected_candidate_and_a_date_and_is_final(self):
        candidate = self.make_candidate(self.make_opening())
        url = f'{CANDIDATES}{candidate["id"]}/move/'
        self.assertEqual(self.api.post(url, {'stage': 'joined', 'joining_date': '2026-12-15'},
                                       format='json').status_code, 400)          # still applied
        self.api.post(url, {'stage': 'selected'}, format='json')
        self.assertEqual(self.api.post(url, {'stage': 'joined'}, format='json').status_code, 400)  # no date
        self.assertEqual(self.api.post(url, {'stage': 'joined', 'joining_date': '2026-12-15'},
                                       format='json').status_code, 200)
        self.assertEqual(self.api.post(url, {'stage': 'rejected', 'rejection_reason': 'x'},
                                       format='json').status_code, 400)

    def test_offer_sets_the_offer_date(self):
        candidate = self.make_candidate(self.make_opening())
        response = self.api.post(f'{CANDIDATES}{candidate["id"]}/move/', {'stage': 'offered'}, format='json')
        self.assertEqual(response.json()['offer_date'], timezone.now().date().isoformat())

    def test_filters_and_search(self):
        opening = self.make_opening()
        a = self.make_candidate(opening, name='Anil Shah', mobile='9000000001')
        self.make_candidate(opening, name='Bina Rao', mobile='9000000002')
        self.api.post(f'{CANDIDATES}{a["id"]}/move/', {'stage': 'shortlisted'}, format='json')
        names = lambda r: [c['name'] for c in r.json()['results']]
        self.assertEqual(names(self.api.get(CANDIDATES, {'stage': 'shortlisted'})), ['Anil Shah'])
        self.assertEqual(names(self.api.get(CANDIDATES, {'search': 'bina'})), ['Bina Rao'])
        self.assertEqual(len(names(self.api.get(CANDIDATES, {'active': 'true'}))), 2)

    def test_only_hr_sees_candidates(self):
        candidate = self.make_candidate(self.make_opening())
        self.as_user(self.panel1)
        self.assertEqual(self.api.get(CANDIDATES).status_code, 404)
        self.assertEqual(self.api.get(f'{CANDIDATES}{candidate["id"]}/').status_code, 404)

    def test_excel_export(self):
        opening = self.make_opening()
        self.make_candidate(opening, name='Anil Shah')
        response = self.api.get(CANDIDATES + 'excel/')
        self.assertEqual(response.status_code, 200)
        sheet = load_workbook(BytesIO(response.content)).active
        self.assertEqual(sheet['B2'].value, 'Anil Shah')


class ResumeTests(Base):
    def upload(self, name, content=b'%PDF-1.4 test', **extra):
        opening = self.make_opening()
        return self.api.post(CANDIDATES, {
            'opening': opening['id'], 'name': 'With CV', 'resume': SimpleUploadedFile(name, content), **extra,
        }, format='multipart')

    def test_resume_is_served_through_the_api_not_a_media_path(self):
        import tempfile
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            response = self.upload('cv.pdf')
            self.assertEqual(response.status_code, 201, response.content)
            body = response.json()
            self.assertTrue(body['has_resume'])
            self.assertNotIn('media', body['resume_url'])
            self.assertNotIn('cv', body['resume_name'])          # stored under a random name
            download = self.api.get(body['resume_url'])
            self.assertEqual(download.status_code, 200)
            self.assertEqual(b''.join(download.streaming_content), b'%PDF-1.4 test')

    def test_bad_extension_and_big_files_are_refused(self):
        self.assertEqual(self.upload('virus.exe').status_code, 400)
        self.assertEqual(self.upload('big.pdf', content=b'0' * (5 * 1024 * 1024 + 1)).status_code, 400)

    def test_resume_missing_is_404(self):
        candidate = self.make_candidate(self.make_opening())
        self.assertEqual(self.api.get(f'{CANDIDATES}{candidate["id"]}/resume/').status_code, 404)


class InterviewTests(Base):
    def setUp(self):
        super().setUp()
        self.opening = self.make_opening()
        self.candidate = self.make_candidate(self.opening)

    def test_scheduling_numbers_the_round_and_moves_the_candidate(self):
        first = self.schedule(self.candidate)
        second = self.schedule(self.candidate, round_type='Final')
        self.assertEqual((first['round_no'], second['round_no']), (1, 2))
        self.assertEqual(Candidate.objects.get(pk=self.candidate['id']).stage, 'interview')
        self.assertEqual([p['interviewer_name'] for p in first['panel']], ['Rcpanel1', 'Rcpanel2'])

    def test_panel_is_required_and_candidate_must_be_in_the_pipeline(self):
        response = self.api.post(INTERVIEWS, {'candidate': self.candidate['id'],
                                              'scheduled_at': '2026-12-01T11:00:00'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.api.post(f'{CANDIDATES}{self.candidate["id"]}/move/',
                      {'stage': 'rejected', 'rejection_reason': 'x'}, format='json')
        response = self.api.post(INTERVIEWS, {
            'candidate': self.candidate['id'], 'scheduled_at': '2026-12-01T11:00:00',
            'panel_ids': [self.panel1.pk]}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_interviewer_sees_only_their_own_interviews(self):
        mine = self.schedule(self.candidate, panel=[self.panel1])
        theirs = self.schedule(self.candidate, panel=[self.panel2])
        self.as_user(self.panel1)
        ids = [i['id'] for i in self.api.get(INTERVIEWS).json()['results']]
        self.assertEqual(ids, [mine['id']])
        self.assertEqual(self.api.get(f'{INTERVIEWS}{theirs["id"]}/').status_code, 404)
        self.as_user(self.stranger)
        self.assertEqual(self.api.get(INTERVIEWS).json()['results'], [])

    def test_interviewer_cannot_schedule_or_change_anything(self):
        interview = self.schedule(self.candidate, panel=[self.panel1])
        self.as_user(self.panel1)
        self.assertEqual(self.api.post(INTERVIEWS, {}, format='json').status_code, 404)
        self.assertEqual(self.api.patch(f'{INTERVIEWS}{interview["id"]}/', {'location': 'x'},
                                        format='json').status_code, 404)
        self.assertEqual(self.api.delete(f'{INTERVIEWS}{interview["id"]}/').status_code, 404)

    def test_feedback_needs_every_criterion_and_a_panel_seat(self):
        interview = self.schedule(self.candidate, panel=[self.panel1])
        url = f'{INTERVIEWS}{interview["id"]}/feedback/'
        self.as_user(self.panel1)
        partial = {'recommendation': 'yes', 'ratings': self.ratings(self.opening, 4)}
        self.assertEqual(self.api.post(url, partial, format='json').status_code, 400)
        bad_rating = {'recommendation': 'yes', 'ratings': self.ratings(self.opening, 4, 9)}
        self.assertEqual(self.api.post(url, bad_rating, format='json').status_code, 400)
        self.as_user(self.hr)                                     # HR is not on the panel
        full = {'recommendation': 'yes', 'ratings': self.ratings(self.opening, 4, 3)}
        self.assertEqual(self.api.post(url, full, format='json').status_code, 404)

    def test_scores_are_weighted_and_the_interview_completes_when_all_have_answered(self):
        interview = self.schedule(self.candidate)
        url = f'{INTERVIEWS}{interview["id"]}/feedback/'
        self.as_user(self.panel1)           # weights 5 and 3: (5*5 + 3*3) / 8 = 4.25
        response = self.api.post(url, {'recommendation': 'strong_yes', 'ratings': self.ratings(self.opening, 5, 3)},
                                 format='json')
        self.assertEqual(response.json()['score'], 4.25)
        self.assertEqual(Interview.objects.get(pk=interview['id']).status, 'scheduled')   # panel2 still owes
        self.as_user(self.panel2)           # (2*5 + 3*3) / 8 = 2.375
        self.api.post(url, {'recommendation': 'no', 'ratings': self.ratings(self.opening, 2, 3)}, format='json')
        self.assertEqual(Interview.objects.get(pk=interview['id']).status, 'completed')
        self.as_user(self.hr)
        body = self.api.get(f'{INTERVIEWS}{interview["id"]}/').json()
        self.assertEqual(body['score'], 3.31)            # mean of 4.25 and 2.375, rounded to 2 places
        self.assertEqual(len(body['feedbacks']), 2)
        candidate = self.api.get(f'{CANDIDATES}{self.candidate["id"]}/').json()
        self.assertEqual(candidate['score'], 3.31)
        self.assertEqual(candidate['interview_count'], 1)

    def test_an_interviewer_cannot_see_other_scorecards_or_the_score(self):
        interview = self.schedule(self.candidate)
        url = f'{INTERVIEWS}{interview["id"]}/feedback/'
        self.as_user(self.panel2)
        self.api.post(url, {'recommendation': 'no', 'ratings': self.ratings(self.opening, 2, 2)}, format='json')
        self.as_user(self.panel1)
        body = self.api.get(f'{INTERVIEWS}{interview["id"]}/').json()
        self.assertEqual(body['my_feedback'], 'pending')
        self.assertEqual(body['feedbacks'][0]['interviewer'], self.panel1.pk)
        self.assertEqual(len(body['feedbacks']), 1)
        self.assertIsNone(body['score'])

    def test_feedback_can_be_edited_and_replaces_the_old_ratings(self):
        interview = self.schedule(self.candidate, panel=[self.panel1])
        url = f'{INTERVIEWS}{interview["id"]}/feedback/'
        self.as_user(self.panel1)
        self.api.post(url, {'recommendation': 'no', 'ratings': self.ratings(self.opening, 1, 1)}, format='json')
        self.api.post(url, {'recommendation': 'yes', 'ratings': self.ratings(self.opening, 5, 5)}, format='json')
        self.assertEqual(FeedbackRating.objects.count(), 2)
        self.assertEqual(FeedbackRating.objects.filter(rating=5).count(), 2)

    def test_cancelled_interview_takes_no_feedback_and_does_not_count(self):
        interview = self.schedule(self.candidate, panel=[self.panel1])
        self.api.post(f'{INTERVIEWS}{interview["id"]}/cancel/', {'reason': 'Panel unavailable'}, format='json')
        self.as_user(self.panel1)
        response = self.api.post(f'{INTERVIEWS}{interview["id"]}/feedback/', {
            'recommendation': 'yes', 'ratings': self.ratings(self.opening, 4, 4)}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_panel_member_with_feedback_cannot_be_removed(self):
        interview = self.schedule(self.candidate)
        self.as_user(self.panel1)
        self.api.post(f'{INTERVIEWS}{interview["id"]}/feedback/', {
            'recommendation': 'yes', 'ratings': self.ratings(self.opening, 4, 4)}, format='json')
        self.as_user(self.hr)
        url = f'{INTERVIEWS}{interview["id"]}/'
        self.assertEqual(self.api.patch(url, {'panel_ids': [self.panel2.pk]}, format='json').status_code, 400)
        response = self.api.patch(url, {'panel_ids': [self.panel1.pk]}, format='json')   # drops panel2, who owes
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.json()['panel']), 1)

    def test_panel_can_read_the_resume_but_a_stranger_cannot(self):
        import tempfile
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            opening = self.make_opening(title='With CV')
            candidate = self.api.post(CANDIDATES, {
                'opening': opening['id'], 'name': 'CV Person',
                'resume': SimpleUploadedFile('cv.pdf', b'%PDF-1.4 x')}, format='multipart').json()
            interview = self.schedule(candidate, panel=[self.panel1])
            self.as_user(self.panel1)
            download = self.api.get(f'{INTERVIEWS}{interview["id"]}/resume/')
            self.assertEqual(download.status_code, 200)
            download.close()                      # Windows will not delete a file that is still open
            self.as_user(self.stranger)
            self.assertEqual(self.api.get(f'{INTERVIEWS}{interview["id"]}/resume/').status_code, 404)

    def test_awaiting_my_feedback_filter_and_summary_badge(self):
        past = (timezone.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S')
        self.schedule(self.candidate, panel=[self.panel1], scheduled_at=past)
        self.as_user(self.panel1)
        waiting = self.api.get(INTERVIEWS, {'awaiting_my_feedback': 'true'}).json()['results']
        self.assertEqual(len(waiting), 1)
        summary = self.api.get(SUMMARY).json()
        self.assertEqual(summary['my_feedback_pending'], 1)
        self.assertNotIn('open_openings', summary)                  # pipeline numbers are HR-only

    def test_hr_summary_has_the_pipeline_numbers(self):
        summary = self.api.get(SUMMARY).json()
        self.assertEqual(summary['open_openings'], 1)
        self.assertEqual(summary['active_candidates'], 1)
        self.assertEqual(summary['stage_counts'], {'applied': 1})


class CancelRescheduleTests(Base):
    def setUp(self):
        super().setUp()
        self.opening = self.make_opening()
        self.candidate = self.make_candidate(self.opening)
        self.interview = self.schedule(self.candidate)
        self.url = f'{INTERVIEWS}{self.interview["id"]}/'

    def test_reschedule_moves_the_time_and_keeps_the_history(self):
        response = self.api.post(self.url + 'reschedule/', {
            'scheduled_at': '2026-12-05T15:30:00', 'reason': 'Candidate had a train delay',
            'location': 'Conference room'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body['scheduled_at'][:16], '2026-12-05T15:30')
        self.assertEqual(body['location'], 'Conference room')
        self.assertEqual(body['status'], 'scheduled')
        self.assertEqual(body['reschedule_count'], 1)
        entry = body['history'][0]
        self.assertEqual(entry['action'], 'rescheduled')
        self.assertEqual(entry['old_time'][:16], '2026-12-01T11:00')
        self.assertEqual(entry['reason'], 'Candidate had a train delay')

    def test_rescheduling_to_the_same_time_is_refused(self):
        response = self.api.post(self.url + 'reschedule/', {'scheduled_at': '2026-12-01T11:00:00'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_cancel_needs_a_reason_and_records_it(self):
        self.assertEqual(self.api.post(self.url + 'cancel/', {}, format='json').status_code, 400)
        self.assertEqual(self.api.post(self.url + 'cancel/', {'reason': '  '}, format='json').status_code, 400)
        response = self.api.post(self.url + 'cancel/', {'reason': 'Position on hold'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body['status'], 'cancelled')
        self.assertEqual(body['cancel_reason'], 'Position on hold')
        self.assertEqual(body['history'][0]['action'], 'cancelled')

    def test_a_cancelled_interview_can_be_rescheduled_and_is_scheduled_again(self):
        self.api.post(self.url + 'cancel/', {'reason': 'Sick'}, format='json')
        response = self.api.post(self.url + 'reschedule/', {'scheduled_at': '2026-12-08T10:00:00'}, format='json')
        body = response.json()
        self.assertEqual(body['status'], 'scheduled')
        self.assertEqual(body['cancel_reason'], '')
        self.assertEqual([h['action'] for h in body['history']], ['rescheduled', 'cancelled'])

    def test_cancelling_twice_or_a_completed_interview_is_refused(self):
        self.api.post(self.url + 'cancel/', {'reason': 'Sick'}, format='json')
        self.assertEqual(self.api.post(self.url + 'cancel/', {'reason': 'Again'}, format='json').status_code, 400)
        self.api.post(self.url + 'set-status/', {'status': 'completed'}, format='json')
        self.assertEqual(self.api.post(
            self.url + 'reschedule/', {'scheduled_at': '2026-12-09T10:00:00'}, format='json').status_code, 400)

    def test_nothing_can_move_once_feedback_is_in(self):
        self.as_user(self.panel1)
        self.api.post(self.url + 'feedback/', {
            'recommendation': 'yes', 'ratings': self.ratings(self.opening, 4, 4)}, format='json')
        self.as_user(self.hr)
        self.assertEqual(self.api.post(self.url + 'cancel/', {'reason': 'x'}, format='json').status_code, 400)
        self.assertEqual(self.api.post(
            self.url + 'reschedule/', {'scheduled_at': '2026-12-09T10:00:00'}, format='json').status_code, 400)

    def test_set_status_will_not_cancel_and_status_cannot_be_patched(self):
        self.assertEqual(self.api.post(self.url + 'set-status/', {'status': 'cancelled'}, format='json').status_code, 400)
        self.api.patch(self.url, {'status': 'cancelled'}, format='json')
        self.assertEqual(self.api.get(self.url).json()['status'], 'scheduled')

    def test_editing_the_time_in_the_edit_dialog_is_logged_too(self):
        self.api.patch(self.url, {'scheduled_at': '2026-12-02T09:00:00'}, format='json')
        body = self.api.get(self.url).json()
        self.assertEqual(body['reschedule_count'], 1)
        self.assertEqual(body['history'][0]['new_time'][:16], '2026-12-02T09:00')

    def test_only_hr_can_cancel_or_reschedule_and_panel_sees_no_history(self):
        self.api.post(self.url + 'reschedule/', {'scheduled_at': '2026-12-05T15:30:00', 'reason': 'private'},
                      format='json')
        self.as_user(self.panel1)
        self.assertEqual(self.api.post(self.url + 'cancel/', {'reason': 'x'}, format='json').status_code, 404)
        self.assertEqual(self.api.post(
            self.url + 'reschedule/', {'scheduled_at': '2026-12-06T10:00:00'}, format='json').status_code, 404)
        body = self.api.get(self.url).json()
        self.assertEqual(body['history'], [])
        self.assertEqual(body['reschedule_count'], 1)                # the panel can see it moved, not why

    def test_cancelled_interview_shows_its_reason_to_the_panel(self):
        self.api.post(self.url + 'cancel/', {'reason': 'Position on hold'}, format='json')
        self.as_user(self.panel1)
        body = self.api.get(self.url).json()
        self.assertEqual(body['status'], 'cancelled')
        self.assertEqual(body['cancel_reason'], 'Position on hold')


class HrDepartmentTests(Base):
    """Users in the 'hr' department get HR access without Staff status."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from employee.models import Department
        cls.hr_dept = Department.objects.create(department_name='HR')
        cls.hr_member = User.objects.create_user('rchrdept', 'rchrdept@example.com', 'x')
        cls.hr_dept.user.add(cls.hr_member)

    def test_department_member_runs_recruitment_without_staff_status(self):
        self.assertFalse(self.hr_member.is_staff)
        self.as_user(self.hr_member)
        opening = self.make_opening(title='By HR dept')
        candidate = self.make_candidate(opening)
        self.schedule(candidate)
        self.assertEqual(self.api.get(OPENINGS).status_code, 200)
        self.assertEqual(len(self.api.get(INTERVIEWS).json()['results']), 1)
        self.assertIn('open_openings', self.api.get(SUMMARY).json())

    def test_department_name_is_case_insensitive(self):
        self.hr_dept.department_name = 'hr'
        self.hr_dept.save()
        self.as_user(self.hr_member)
        self.assertEqual(self.api.get(OPENINGS).status_code, 200)

    def test_inactive_member_and_other_departments_get_nothing(self):
        from employee.models import Department
        other = Department.objects.create(department_name='sidebank')
        other.user.add(self.stranger)
        self.as_user(self.stranger)
        self.assertEqual(self.api.get(OPENINGS).status_code, 404)
        self.hr_member.is_active = False
        self.hr_member.save()
        self.as_user(User.objects.get(pk=self.hr_member.pk))
        from crm.querysets import is_hr
        self.assertFalse(is_hr(User.objects.get(pk=self.hr_member.pk)))

    def test_attendance_and_holiday_rules_follow_the_same_check(self):
        from attendance.permissions import IsAttendanceUser
        from holidaylist.permissions import can_edit_holidays

        class Req:
            def __init__(self, user):
                self.user = user

        self.assertTrue(IsAttendanceUser().has_permission(Req(self.hr_member), None))
        self.assertTrue(can_edit_holidays(self.hr_member))
        self.assertFalse(IsAttendanceUser().has_permission(Req(self.stranger), None))
        self.assertFalse(can_edit_holidays(self.stranger))
        self.assertTrue(can_edit_holidays(self.hr))                 # staff still work
