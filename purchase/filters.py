import django_filters

from . import choices
from .choices import material_category
from .models import Po, PoItem
from customer.models import Customer
from django.contrib.auth.models import User


class PoFilter(django_filters.FilterSet):

    created__gt = django_filters.DateTimeFilter(label="From Date", field_name='created', lookup_expr='gte',
                                                input_formats=("%d/%m/%Y %H:%M",))
    created__lt = django_filters.DateTimeFilter(label="To Date", field_name='created', lookup_expr='lte',
                                                input_formats=("%d/%m/%Y %H:%M",))

    supplier = django_filters.ModelChoiceFilter(queryset=Customer.objects.filter(is_supplier=True))
    approval_pending = django_filters.BooleanFilter(label='approval Pending', field_name="approvedby",
                                                    lookup_expr='isnull')


    class Meta:
        model = Po
        fields = ['id', 'supplier', 'status', 'createdby']



class PoItemFilter(django_filters.FilterSet):
    created__gt = django_filters.DateTimeFilter(label="From Date", field_name='created', lookup_expr='gte',
                                                input_formats=("%d/%m/%Y %H:%M",))
    created__lt = django_filters.DateTimeFilter(label="To Date", field_name='created', lookup_expr='lte',
                                                input_formats=("%d/%m/%Y %H:%M",))

    description = django_filters.CharFilter(label="Po Item", field_name="description", lookup_expr="icontains")
    purchase = django_filters.CharFilter(label="Supplier", field_name="purchaseorder__supplier__name",
                                         lookup_expr="icontains")
    createdby = django_filters.ModelChoiceFilter(label="Created By", field_name="purchaseorder__createdby",
                                                 queryset=User.objects.all())
    approval_pending = django_filters.BooleanFilter(label='approval Pending', field_name="purchaseorder__approvedby",
                                                    lookup_expr='isnull')
    purchaseorder__approvedby = django_filters.ModelChoiceFilter(label="Approved By",
                                                                 field_name="purchaseorder__approvedby",
                                                                 queryset=User.objects.all())
    purchaseorder__status = django_filters.ChoiceFilter(label="Status",
                                                                 field_name="purchaseorder__status",
                                                                 choices=choices.pochoices)

    class Meta:
        model = PoItem
        fields = ['id', "description","category" ]
