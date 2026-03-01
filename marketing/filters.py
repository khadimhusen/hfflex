import django_filters
from .models import Route, RouteCustomer, Lead, Bunch


class LeadFilter(django_filters.FilterSet):
    cityname = django_filters.CharFilter(label='City', field_name='cityname', lookup_expr='icontains')
    customername = django_filters.CharFilter(label='Customer', field_name='customername', lookup_expr='icontains')
    contact = django_filters.CharFilter(label='Contact', field_name='contact_number', lookup_expr='icontains')
    industry = django_filters.CharFilter(label='Industry', field_name='industry', lookup_expr='icontains')

    class Meta:
        model = Lead
        fields = ['lead_active']


class RouteFilter(django_filters.FilterSet):
    class Meta:
        model = Route
        fields = ['route_date', 'marketing_person', 'is_closed']


class BunchFilter(django_filters.FilterSet):

    class Meta:
        model = Bunch
        fields = ["leaduser", "completed"]
