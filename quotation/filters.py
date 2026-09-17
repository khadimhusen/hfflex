import django_filters

from .models import Quotation, QuotationItem
from django.contrib.auth.models import User


class QuotationFilter(django_filters.FilterSet):

    CHOICES = [
                ("None","Unapproved"),
                ("Approved","Approved")]


    marketinperson=User.objects.filter(department__department_name="marketing")


    created__gt = django_filters.DateTimeFilter(label="From Date", field_name='created', lookup_expr='gte',
                                                input_formats=("%d/%m/%Y %H:%M",))
    created__lt = django_filters.DateTimeFilter(label="To Date", field_name='created', lookup_expr='lte',
                                                input_formats=("%d/%m/%Y %H:%M",))

    approved__gt = django_filters.DateTimeFilter(label="Approved From", field_name='approved', lookup_expr='gte',
                                                input_formats=("%d/%m/%Y %H:%M",))
    approved__lt = django_filters.DateTimeFilter(label="Approved Date", field_name='approved', lookup_expr='lte',
                                                input_formats=("%d/%m/%Y %H:%M",))
    partyname = django_filters.CharFilter(field_name='partyname', label='Customer', lookup_expr='icontains')
    address = django_filters.CharFilter(field_name='add', label='Address', lookup_expr='icontains')
    itemname = django_filters.CharFilter(method='filter_itemname', label='Item Name')

    approvedby = django_filters.ChoiceFilter(method='filter_some_field',choices=CHOICES)
    createdby = django_filters.ModelChoiceFilter(
        queryset=User.objects.filter(department__department_name="marketing"),
        label="Created By"
    )

    def filter_itemname(self, queryset, name, value):
        # Quotes with any line item whose job name contains the text. A
        # subquery rather than a join, so a quote with several matching items
        # is still one row (and counted once in the list's total_cost).
        return queryset.filter(
            id__in=QuotationItem.objects.filter(jobname__icontains=value).values('quote_id'),
        )

    def filter_some_field(self, queryset, name, value):
        if value == 'None':  # Filter for None values
            return queryset.filter(**{f'{name}__isnull': True})
        if value == 'Approved':  # Filter for None values
            return queryset.filter(**{f'{name}__isnull': False})
        elif value:  # Filter for other selected values
            return queryset.filter(**{name: value})
        else:  # No filter applied
            return queryset

    class Meta:
        model = Quotation
        fields = ['id',"approvedby"]


