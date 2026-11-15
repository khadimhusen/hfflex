import django_filters
from django.db.models import Q

from .models import MEETING_TYPES, STATUS_CHOICES, Meeting

# An action item is open until it is marked done here or its task is closed.
OPEN_ITEM = Q(action_items__is_done=False) & (
    Q(action_items__task__isnull=True) | Q(action_items__task__is_closed=False))


class MeetingFilter(django_filters.FilterSet):
    meeting_type = django_filters.ChoiceFilter(choices=MEETING_TYPES)
    status = django_filters.ChoiceFilter(choices=STATUS_CHOICES)
    date_from = django_filters.DateFilter(field_name='meeting_date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='meeting_date', lookup_expr='lte')
    attendee = django_filters.NumberFilter(field_name='attendees__user')
    has_open_items = django_filters.BooleanFilter(method='filter_has_open_items')
    mine = django_filters.BooleanFilter(method='filter_mine')

    class Meta:
        model = Meeting
        fields = []

    def filter_has_open_items(self, queryset, name, value):
        with_open = Meeting.objects.filter(OPEN_ITEM).values('pk')
        return queryset.filter(pk__in=with_open) if value else queryset.exclude(pk__in=with_open)

    def filter_mine(self, queryset, name, value):
        """Meetings the current user created or attended."""
        if not value:
            return queryset
        user = self.request.user
        return queryset.filter(Q(created_by=user) | Q(attendees__user=user)).distinct()
