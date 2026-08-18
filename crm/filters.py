from django.db.models import  F
import django_filters
from .models import Deal, Lead, Account, Contact


class DealFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(
        choices=[
            ('not_closed', 'Not Closed'),
            ('won', 'Closed Won'),
            ('lost', 'Closed Lost'),
        ],
        method='filter_status',
    )
    stalled = django_filters.BooleanFilter(field_name='is_stalled')

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

class LeadFilter(django_filters.FilterSet):
    class Meta:
        model = Lead
        fields = {
            'owner': ['exact'],
            'lead_source': ['exact'],
            'is_converted': ['exact'],
        }


class AccountFilter(django_filters.FilterSet):
    class Meta:
        model = Account
        fields = {'owner': ['exact'], 'industry': ['exact']}


class ContactFilter(django_filters.FilterSet):
    class Meta:
        model = Contact
        fields = {'owner': ['exact'], 'account': ['exact']}