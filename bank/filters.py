import django_filters
from .models import Cheque


class ChequeFilter(django_filters.FilterSet):

    cheque__from = django_filters.DateFilter(label="From", field_name='cheque_date', lookup_expr='gte',
                                            input_formats=('%d/%m/%Y',))
    cheque__to = django_filters.DateFilter(label="To", field_name='cheque_date', lookup_expr='lte',
                                            input_formats=('%d/%m/%Y',))
    party=django_filters.CharFilter(label='Party Name',field_name="party",lookup_expr="icontains")
    class Meta:
        model = Cheque
        fields = ["bank","number","party","status","bill_number","lock_record","edited","editedby"]

