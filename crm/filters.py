from datetime import timedelta

from django.db.models import  F
import django_filters
from .models import Deal, Lead, Account, Contact


class CreatedDateFilterSet(django_filters.FilterSet):
    """created_from / created_to: the day a record was created, both days
    included (created_at is a datetime, so "to" runs to the end of that day)."""
    created_from = django_filters.DateFilter(field_name='created_at', lookup_expr='gte')
    created_to = django_filters.DateFilter(method='filter_created_to')

    def filter_created_to(self, queryset, name, value):
        return queryset.filter(created_at__lt=value + timedelta(days=1))


class DealFilter(CreatedDateFilterSet):
    status = django_filters.ChoiceFilter(
        choices=[
            ('not_closed', 'Not Closed'),
            ('won', 'Closed Won'),
            ('lost', 'Closed Lost'),
        ],
        method='filter_status',
    )
    stalled = django_filters.BooleanFilter(field_name='is_stalled')
    # Part of the name, any case: imported cities read "Pune, Maharashtra, India".
    city = django_filters.CharFilter(field_name='city', lookup_expr='icontains')
    # Whole value, any case: the imported data has "INDIAMART", "Indiamart" and
    # "IndiaMart" side by side, and they are one source.
    lead_source = django_filters.CharFilter(field_name='lead_source', lookup_expr='iexact')

    class Meta:
        model = Deal
        fields = {
            'pipeline': ['exact'],
            'stage': ['exact'],
            'owner': ['exact'],
            'deal_type': ['exact'],
            'closing_date': ['gte', 'lte'],
        }

    def filter_status(self, queryset, name, value):
        if value == 'won':
            return queryset.filter(stage__is_won=True)
        if value == 'lost':
            return queryset.filter(stage__is_lost=True)
        if value == 'not_closed':
            return queryset.filter(stage__is_won=False, stage__is_lost=False)
        return queryset

class LeadFilter(CreatedDateFilterSet):
    # Whole value, any case (see DealFilter).
    lead_source = django_filters.CharFilter(field_name='lead_source', lookup_expr='iexact')

    class Meta:
        model = Lead
        fields = {
            'owner': ['exact'],
            'is_converted': ['exact'],
        }


class AccountFilter(django_filters.FilterSet):
    class Meta:
        model = Account
        fields = {'owner': ['exact'], 'industry': ['exact']}


class ContactFilter(django_filters.FilterSet):
    # Part of the name, any case -- same as the deals City filter.
    company = django_filters.CharFilter(field_name='account__name', lookup_expr='icontains')
    city = django_filters.CharFilter(field_name='mailing_city', lookup_expr='icontains')

    class Meta:
        model = Contact
        fields = {'owner': ['exact'], 'account': ['exact']}