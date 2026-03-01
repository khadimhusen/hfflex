import django_filters
from .models import Shift, Activity, ShiftPerson


class ShiftFilter(django_filters.FilterSet):
    date__gt = django_filters.DateFilter(label="From Date", field_name='production_date', lookup_expr='gte',
                                            input_formats=('%d/%m/%Y',))
    date__lt = django_filters.DateFilter(label="To Date", field_name='production_date', lookup_expr='lte',
                                            input_formats=('%d/%m/%Y',))

    class Meta:
        model = Shift
        fields = ['shift', 'machine',]
