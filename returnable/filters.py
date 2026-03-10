import django_filters

from . import choices
from .choices import returnablechoice
from .models import Returnable, ReceivedItem, ReceivedChallan, ChallanItem
from django.contrib.auth.models import User
import django_filters
from .models import ChallanItem
from customer.models import Customer




class ReturnableFilter(django_filters.FilterSet):

    expected_date__gt = django_filters.DateFilter(label="From Date", field_name='expected_date', lookup_expr='gte',
                                                input_formats=("%d/%m/%Y %H:%M",))
    expected_date__lt = django_filters.DateFilter(label="To Date", field_name='expected_date', lookup_expr='lte',
                                                input_formats=("%d/%m/%Y",))

    party_name = django_filters.ModelChoiceFilter(queryset=Customer.objects.filter(is_supplier=True))
    approval_pending = django_filters.BooleanFilter(label='approval Pending', field_name="approvedby",
                                                    lookup_expr='isnull')


    class Meta:
        model = Returnable
        fields = ['id', 'party_name', 'status', 'createdby']



class ChallanItemFilter(django_filters.FilterSet):
    created__gt = django_filters.DateTimeFilter(label="From Date", field_name='created', lookup_expr='gte',
                                                input_formats=("%d/%m/%Y %H:%M",))
    created__lt = django_filters.DateTimeFilter(label="To Date", field_name='created', lookup_expr='lte',
                                                input_formats=("%d/%m/%Y %H:%M",))

    description = django_filters.CharFilter(label="Item", field_name="description", lookup_expr="icontains")
    party = django_filters.CharFilter(label="Party", field_name="returnable__party_name__name",
                                         lookup_expr="icontains")
    createdby = django_filters.ModelChoiceFilter(label="Created By", field_name="returnable__createdby",
                                                 queryset=User.objects.all())


    returnable__status = django_filters.ChoiceFilter(label="Status",
                                                                 field_name="returnable__status",
                                                                 choices=choices.returnablechoice)

    class Meta:
        model = ChallanItem
        fields = ['id', "description","category" ]


# Add this to your existing filters.py

class ChallanItemFilter(django_filters.FilterSet):
    party_name = django_filters.ModelChoiceFilter(
        field_name='returnable__party_name',
        queryset=Customer.objects.filter( is_supplier=True).order_by('name'),
        label='Party Name',
        empty_label='All Parties'
    )
    status = django_filters.ChoiceFilter(
        field_name='returnable__status',
        choices=[
            ('', 'All'),
            ('Dispatched', 'Dispatched'),
            ('Delivered', 'Delivered'),
            ('Received', 'Received'),
            ('Partially received', 'Partially received'),
        ],
        label='Status',
        empty_label=None
    )
    itemname = django_filters.CharFilter(
        lookup_expr='icontains',
        label='Item Name'
    )

    class Meta:
        model = ChallanItem
        fields = ['party_name', 'status', 'itemname']

class ReceivedChallanFilter(django_filters.FilterSet):

    received_date__gt = django_filters.DateFilter(label="From Date", field_name='received_date', lookup_expr='gte',
                                                input_formats=("%d/%m/%Y %H:%M",))
    received_date__lt = django_filters.DateFilter(label="To Date", field_name='received_date', lookup_expr='lte',
                                                input_formats=("%d/%m/%Y",))

    party_name = django_filters.ModelChoiceFilter(queryset=Customer.objects.filter(is_supplier=True))


    class Meta:
        model = ReceivedChallan
        fields = ['id', 'party_name', 'createdby']