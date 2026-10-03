import django_filters
from .models import Shift, Activity, ShiftPerson, DowntimeReport
from production.models import JobQc

from django import forms


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


class ActivityJobFilter(django_filters.FilterSet):
    """Filters for the manpower Job List -- one row per Activity (a job
    worked on in a shift), so the shift's machine/shift/date and the job's
    own details are all filterable."""
    jobid = django_filters.NumberFilter(field_name='jobid__id', label='Job ID')
    itemname = django_filters.CharFilter(field_name='jobid__itemname', label='Item Name',
                                         lookup_expr='icontains')
    customer = django_filters.CharFilter(field_name='jobid__joborder__customer__name', label='Customer',
                                         lookup_expr='icontains')
    date__gt = django_filters.DateFilter(label="From Date", field_name='shift__production_date',
                                         lookup_expr='gte', input_formats=('%d/%m/%Y',))
    date__lt = django_filters.DateFilter(label="To Date", field_name='shift__production_date',
                                         lookup_expr='lte', input_formats=('%d/%m/%Y',))

    class Meta:
        model = Activity
        fields = ['shift__machine', 'shift__shift', 'makeready', 'shift__is_approved']

    def __init__(self, *args, **kwargs):
        super(ActivityJobFilter, self).__init__(*args, **kwargs)
        self.filters['shift__machine'].label = "Machine"
        self.filters['shift__shift'].label = "Shift"
        self.filters['makeready'].label = "Make Ready"
        self.filters['shift__is_approved'].label = "Approved"


class JobQcFilter(django_filters.FilterSet):
    time__gt = django_filters.DateFilter(
        label="From Date",
        field_name='created',
        lookup_expr='date__gte',
        widget=forms.DateInput(attrs={'id': 'id_time__gt'})
    )
    time__lt = django_filters.DateFilter(
        label="To Date",
        field_name='created',
        lookup_expr='date__lte',
        widget=forms.DateInput(attrs={'id': 'id_time__lt'})
    )
    class Meta:
        model = JobQc
        fields = ["createdby","prodreport__prodprocess__process"]