from django.db.models import  F
import django_filters
from .models import Deal, Lead, Account, Contact


class DealFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=[...], method='filter_status')
    stalled = django_filters.BooleanFilter(field_name='is_stalled')
    not_before_stage = django_filters.CharFilter(method='filter_not_before_stage')

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

    def filter_not_before_stage(self, queryset, name, value):
        # value is a stage NAME (e.g. "Calling"); find its order per-deal's own pipeline
        return queryset.filter(stage__order__lt=F('pipeline__stages__order')).filter(
            pipeline__stages__dealstagename__name=value
        ).distinct()



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