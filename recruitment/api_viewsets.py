from datetime import timedelta

from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from . import services
from .api_serializers import (
    CandidateSerializer, FeedbackReadSerializer, FeedbackSubmitSerializer, InterviewSerializer,
    JobOpeningSerializer, MoveSerializer,
)
from .exports import excel_filename, generate_candidates_xlsx
from .filters import CandidateFilter, InterviewFilter, OpeningFilter
from .models import ACTIVE_STAGES, Candidate, Interview, InterviewFeedback, JobOpening
from .permissions import IsHR, IsLoggedIn, is_hr, visible_interviews

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def resume_response(candidate):
    if not candidate.resume:
        raise Http404('No resume uploaded.')
    try:
        handle = candidate.resume.open('rb')
    except FileNotFoundError:
        raise Http404('The resume file is missing.')
    return FileResponse(handle, as_attachment=False, filename=candidate.resume.name.rsplit('/', 1)[-1])


class JobOpeningViewSet(viewsets.ModelViewSet):
    """Requirements. HR only."""
    permission_classes = [IsHR]
    serializer_class = JobOpeningSerializer
    filterset_class = OpeningFilter
    search_fields = ['number', 'title', 'department', 'location']

    def get_queryset(self):
        return JobOpening.objects.select_related('hiring_manager', 'created_by').prefetch_related(
            'criteria').annotate(
            candidate_count=Count('candidates', distinct=True),
            active_count=Count('candidates', filter=Q(candidates__stage__in=ACTIVE_STAGES), distinct=True),
            joined_count=Count('candidates', filter=Q(candidates__stage='joined'), distinct=True),
        ).order_by('-opened_date', '-id')

    def perform_destroy(self, instance):
        if instance.candidates.exists():
            raise ValidationError('This opening has candidates. Close it instead of deleting it.')
        instance.delete()

    @action(detail=False, methods=['get'], url_path='criteria-templates')
    def criteria_templates(self, request):
        """Ready-made scorecards (e.g. Production Manager) to load into a new opening."""
        return Response(services.criteria_templates())


class CandidateViewSet(viewsets.ModelViewSet):
    """Candidates and their pipeline. HR only; compensation and notes stay here."""
    permission_classes = [IsHR]
    serializer_class = CandidateSerializer
    filterset_class = CandidateFilter
    search_fields = ['name', 'mobile', 'email', 'current_company', 'current_designation', 'opening__number',
                     'opening__title']

    def get_queryset(self):
        return Candidate.objects.select_related('opening', 'created_by').prefetch_related(
            'stage_logs__changed_by', 'interviews__feedbacks__ratings__criterion')

    def perform_destroy(self, instance):
        if instance.resume:
            instance.resume.delete(save=False)
        instance.delete()

    @action(detail=True, methods=['post'])
    def move(self, request, pk=None):
        """Move along the pipeline: {stage, note?, rejection_reason?, joining_date?}."""
        candidate = self.get_object()
        data = MoveSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        services.move_stage(candidate, v['stage'], request.user, note=v['note'],
                            rejection_reason=v['rejection_reason'], joining_date=v.get('joining_date'))
        candidate = self.get_queryset().get(pk=candidate.pk)
        return Response(self.get_serializer(candidate).data)

    @action(detail=True, methods=['get'])
    def resume(self, request, pk=None):
        return resume_response(self.get_object())

    @action(detail=False, methods=['get'])
    def excel(self, request):
        """The candidates list (with the current filters) as an .xlsx."""
        candidates = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type=XLSX)
        response['Content-Disposition'] = f'attachment; filename="{excel_filename()}"'
        generate_candidates_xlsx(response, candidates)
        return response


class InterviewViewSet(viewsets.ModelViewSet):
    """HR schedules and manages interviews; an interviewer sees only the ones they
    are on the panel of, and can read the resume and submit their own scorecard."""
    serializer_class = InterviewSerializer
    filterset_class = InterviewFilter
    search_fields = ['candidate__name', 'candidate__opening__title', 'location']

    def get_permissions(self):
        if self.action in ('list', 'retrieve', 'feedback', 'resume'):
            return [IsLoggedIn()]
        return [IsHR()]

    def get_queryset(self):
        qs = Interview.objects.select_related(
            'candidate', 'candidate__opening', 'created_by').prefetch_related(
            'feedbacks__interviewer', 'feedbacks__ratings__criterion', 'candidate__opening__criteria')
        return visible_interviews(self.request.user, qs).order_by('-scheduled_at', '-id')

    @action(detail=True, methods=['post'])
    def feedback(self, request, pk=None):
        """The logged-in panel member submits (or edits) their own scorecard."""
        interview = self.get_object()
        if interview.status == 'cancelled':
            raise ValidationError('This interview was cancelled.')
        mine = InterviewFeedback.objects.filter(interview=interview, interviewer=request.user).first()
        if mine is None:
            raise PermissionDenied('You are not on the panel of this interview.')
        data = FeedbackSubmitSerializer(data=request.data, context={'interview': interview})
        data.is_valid(raise_exception=True)
        v = data.validated_data
        services.submit_feedback(mine, v['recommendation'], v['comments'], v.get('ratings', []))
        mine = InterviewFeedback.objects.prefetch_related('ratings__criterion').get(pk=mine.pk)
        return Response(FeedbackReadSerializer(mine).data)

    @action(detail=True, methods=['post'], url_path='set-status')
    def set_status(self, request, pk=None):
        """HR: mark an interview completed, cancelled or no-show (or put it back to scheduled)."""
        interview = self.get_object()
        status = request.data.get('status')
        if status not in dict(Interview._meta.get_field('status').choices):
            raise ValidationError({'status': 'Unknown status.'})
        interview.status = status
        interview.save(update_fields=['status', 'updated_at'])
        return Response(self.get_serializer(interview).data)

    @action(detail=True, methods=['get'])
    def resume(self, request, pk=None):
        """The candidate's resume, for the people interviewing them."""
        return resume_response(self.get_object().candidate)


@api_view(['GET'])
@permission_classes([IsLoggedIn])
def summary(request):
    """Counts for the recruitment page and the menu badge. Everyone gets how many
    scorecards they still owe; HR also gets the pipeline numbers."""
    user = request.user
    now = timezone.now()
    owed = Interview.objects.filter(
        feedbacks__interviewer=user, feedbacks__submitted_at__isnull=True,
        status__in=['scheduled', 'completed'], scheduled_at__lte=now).distinct().count()
    data = {'my_feedback_pending': owed}
    if is_hr(user):
        today = timezone.now().date()
        upcoming = Interview.objects.filter(status='scheduled', scheduled_at__date__gte=today)
        data.update({
            'open_openings': JobOpening.objects.filter(status='open').count(),
            'active_candidates': Candidate.objects.filter(stage__in=ACTIVE_STAGES).count(),
            'interviews_today': upcoming.filter(scheduled_at__date=today).count(),
            'interviews_next_7_days': upcoming.filter(scheduled_at__date__lte=today + timedelta(days=7)).count(),
            'offers_pending': Candidate.objects.filter(stage='offered').count(),
            'joined_last_30_days': Candidate.objects.filter(
                stage='joined', stage_logs__to_stage='joined',
                stage_logs__changed_at__gte=now - timedelta(days=30)).distinct().count(),
            'stage_counts': {row['stage']: row['n'] for row in
                             Candidate.objects.values('stage').annotate(n=Count('id'))},
        })
    return Response(data)
