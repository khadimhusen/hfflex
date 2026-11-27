import django_filters

from .models import ACTIVE_STAGES, INTERVIEW_STATUS, OPENING_STATUS, SOURCES, STAGES, Candidate, Interview, JobOpening


class OpeningFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=OPENING_STATUS)
    department = django_filters.CharFilter(lookup_expr='iexact')

    class Meta:
        model = JobOpening
        fields = []


class CandidateFilter(django_filters.FilterSet):
    opening = django_filters.NumberFilter()
    stage = django_filters.ChoiceFilter(choices=STAGES)
    source = django_filters.ChoiceFilter(choices=SOURCES)
    active = django_filters.BooleanFilter(method='filter_active')
    created_from = django_filters.DateFilter(field_name='created_at', lookup_expr='date__gte')
    created_to = django_filters.DateFilter(field_name='created_at', lookup_expr='date__lte')

    class Meta:
        model = Candidate
        fields = []

    def filter_active(self, queryset, name, value):
        """true: still in the pipeline. false: joined, rejected or withdrawn."""
        return queryset.filter(stage__in=ACTIVE_STAGES) if value else queryset.exclude(stage__in=ACTIVE_STAGES)


class InterviewFilter(django_filters.FilterSet):
    candidate = django_filters.NumberFilter()
    opening = django_filters.NumberFilter(field_name='candidate__opening')
    status = django_filters.ChoiceFilter(choices=INTERVIEW_STATUS)
    date_from = django_filters.DateFilter(field_name='scheduled_at', lookup_expr='date__gte')
    date_to = django_filters.DateFilter(field_name='scheduled_at', lookup_expr='date__lte')
    mine = django_filters.BooleanFilter(method='filter_mine')
    awaiting_my_feedback = django_filters.BooleanFilter(method='filter_awaiting')

    class Meta:
        model = Interview
        fields = []

    def filter_mine(self, queryset, name, value):
        """Interviews the current user is on the panel of."""
        if not value:
            return queryset
        return queryset.filter(feedbacks__interviewer=self.request.user).distinct()

    def filter_awaiting(self, queryset, name, value):
        """Interviews where the current user still has to submit feedback."""
        if not value:
            return queryset
        return queryset.filter(feedbacks__interviewer=self.request.user, feedbacks__submitted_at__isnull=True,
                               status__in=['scheduled', 'completed']).distinct()
