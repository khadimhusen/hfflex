import django_filters
from .models import Customer, Address
from django.db.models import Q



class CustomerFilter(django_filters.FilterSet):

    created__gt = django_filters.DateFilter(label="From", field_name='created', lookup_expr='gt',
                                            input_formats=('%d/%m/%Y',))
    created__lt = django_filters.DateFilter(label="To", field_name='created', lookup_expr='lt',
                                            input_formats=('%d/%m/%Y',))
    customername = django_filters.CharFilter(label='Customer', field_name='name', lookup_expr='icontains')

    class Meta:
        model = Customer
        fields = ['is_customer','is_supplier']

class CustomerAddressFilter(django_filters.FilterSet):

    address = django_filters.CharFilter(label="Address", method='filter_by_all_fields')
    partyname = django_filters.CharFilter(label='Party Name', field_name='customer__name', lookup_expr='icontains')
    is_customer = django_filters.BooleanFilter(label='is_customer', field_name='customer__is_customer')
    is_supplier = django_filters.BooleanFilter(label='is_supplier', field_name='customer__is_supplier')
    pincode = django_filters.RangeFilter()



    class Meta:
        model = Address
        fields = ["pincode" ]

    def filter_by_all_fields(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(add1__icontains=value) | Q(add2__icontains=value)
        )