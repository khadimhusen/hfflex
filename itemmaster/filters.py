import django_filters
from .models import ItemMaster


class ItemmasterFilter(django_filters.FilterSet):

    created__gt = django_filters.DateFilter(label="From", field_name='created', lookup_expr='gte',
                                            input_formats=('%d/%m/%Y',))
    created__lt = django_filters.DateFilter(label="To", field_name='created', lookup_expr='lte',
                                            input_formats=('%d/%m/%Y',))
    itemname=django_filters.CharFilter(label='Itemmaster', field_name='itemname', lookup_expr='icontains')
    itemcustomer=django_filters.CharFilter(label='Customer', field_name='itemcustomer__name', lookup_expr='icontains')
    packsize=django_filters.CharFilter(label="Pack Size", field_name='packsize',lookup_expr='icontains')
    circum = django_filters.NumberFilter(label='circum', field_name='cyl_circum')

    class Meta:
        model = ItemMaster
        fields = ['active', 'film_size','createdby']
