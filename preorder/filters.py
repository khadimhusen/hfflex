import django_filters
from .models import PreOrder


class PreOrderFilter(django_filters.FilterSet):
    schedule_from = django_filters.DateFilter(label="schedule From", field_name='schedule', lookup_expr='gte',
                                            input_formats=('%d/%m/%Y',))
    schedule_to = django_filters.DateFilter(label="Schedule To", field_name='schedule', lookup_expr='lte',
                                            input_formats=('%d/%m/%Y',))
    customer = django_filters.CharFilter(field_name='customer', label="Customer", lookup_expr='icontains')

    class Meta:
        model = PreOrder
        fields = ['final_submition','editedby']
