import django_filters
from django.db.models import Q

from .models import AttendanceDay, PunchLog


class PunchFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name='punched_at', lookup_expr='date__gte')
    date_to = django_filters.DateFilter(field_name='punched_at', lookup_expr='date__lte')
    unmatched = django_filters.BooleanFilter(method='filter_unmatched')
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        model = PunchLog
        fields = ['worker', 'emp_code', 'source']

    def filter_unmatched(self, qs, name, value):
        return qs.filter(worker__isnull=bool(value))

    def filter_search(self, qs, name, value):
        return qs.filter(Q(emp_code__icontains=value) | Q(worker__worker_name__icontains=value))


class DayFilter(django_filters.FilterSet):
    date_from = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='date', lookup_expr='lte')
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        model = AttendanceDay
        fields = ['worker', 'date', 'status', 'shift', 'is_manual']

    def filter_search(self, qs, name, value):
        return qs.filter(Q(worker__worker_name__icontains=value) | Q(worker__emp_code__icontains=value))
