import django_filters
from .models import Shift, Activity, ShiftPerson, DowntimeReport


class ShiftFilter(django_filters.FilterSet):
    date__gt = django_filters.DateFilter(label="From Date", field_name='production_date', lookup_expr='gte',
                                         input_formats=('%d/%m/%Y',))
    date__lt = django_filters.DateFilter(label="To Date", field_name='production_date', lookup_expr='lte',
                                         input_formats=('%d/%m/%Y',))

    class Meta:
        model = Shift
        fields = ['shift', 'machine', 'is_approved']


class DowntimeFilter(django_filters.FilterSet):
    date__gt = django_filters.DateFilter(label="From Date", field_name='activity__shift__production_date', lookup_expr='gte',
                                         input_formats=('%d/%m/%Y',))
    date__lt = django_filters.DateFilter(label="To Date", field_name='activity__shift__production_date', lookup_expr='lte',
                                         input_formats=('%d/%m/%Y',))
    time__gt = django_filters.NumberFilter(label="From Time", field_name='downtime', lookup_expr='gte')
    time__lt = django_filters.NumberFilter(label="To Time", field_name='downtime', lookup_expr='lte')

    class Meta:
        model = DowntimeReport
        fields = ["activity__shift__machine","activity__shift__shift","reason"]

    def __init__(self, *args, **kwargs):
        super(DowntimeFilter, self).__init__(*args, **kwargs)
        self.filters['activity__shift__machine'].label = "Machine"
        self.filters['activity__shift__shift'].label = "Shift"
