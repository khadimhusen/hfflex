import django_filters
from .models import ProdReport, Stockdetail, DispatchRegister, Inward


class ProdReportFilter(django_filters.FilterSet):
    created__gt = django_filters.DateFilter(label="From", field_name='created', lookup_expr='gte',
                                            input_formats=('%d/%m/%Y',))
    created__lt = django_filters.DateFilter(label="To", field_name='created', lookup_expr='lte',
                                            input_formats=('%d/%m/%Y',))

    class Meta:
        model = ProdReport
        fields = ['prodprocess__process', 'prodprocess__status', 'checked','approved']


class StockFilter(django_filters.FilterSet):
    film__gte = django_filters.NumberFilter(field_name='size', label='From size', lookup_expr='gte')
    film__lte = django_filters.NumberFilter(field_name='size', label='To size', lookup_expr='lte')
    mic__gte = django_filters.NumberFilter(field_name='micron', label='From mic', lookup_expr='gte')
    mic__lte = django_filters.NumberFilter(field_name='micron', label='To mic', lookup_expr='lte')
    balance = django_filters.RangeFilter()
    available= django_filters.RangeFilter()

    class Meta:
        model = Stockdetail
        fields = ["id", 'materialname', 'item_mat_type', 'item_grade', 'qc_status', "balance","available"]


class DispatchFilter(django_filters.FilterSet):
    created__gt = django_filters.DateFilter(label="From", field_name='dispatchdate', lookup_expr='gte',
                                            input_formats=('%d/%m/%Y',))
    created__lt = django_filters.DateFilter(label="To", field_name='dispatchdate', lookup_expr='lte',
                                            input_formats=('%d/%m/%Y',))
    customername = django_filters.CharFilter(label='Customer', field_name='customer__name', lookup_expr='icontains')

    class Meta:
        model = DispatchRegister
        fields = ["id", ]


class InwardFilter(django_filters.FilterSet):
    created__gt = django_filters.DateFilter(label="From", field_name='inwarddate', lookup_expr='gte',
                                            input_formats=('%d/%m/%Y',))
    created__lt = django_filters.DateFilter(label="To", field_name='inwarddate', lookup_expr='lte',
                                            input_formats=('%d/%m/%Y',))
    supplier = django_filters.CharFilter(label='Supplir',
                                         field_name='supplier__name',
                                         lookup_expr='icontains')

    class Meta:
        model = Inward
        fields = []
