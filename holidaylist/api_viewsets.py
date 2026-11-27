from datetime import date as date_type

import django_filters
from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import services
from .api_serializers import HolidaySerializer
from .models import KINDS, Holiday
from .permissions import HolidayPermission


class HolidayFilter(django_filters.FilterSet):
    year = django_filters.NumberFilter(field_name='date__year')
    kind = django_filters.ChoiceFilter(choices=KINDS)
    date_from = django_filters.DateFilter(field_name='date', lookup_expr='gte')
    date_to = django_filters.DateFilter(field_name='date', lookup_expr='lte')

    class Meta:
        model = Holiday
        fields = []


class HolidayViewSet(viewsets.ModelViewSet):
    """The holiday list. Anyone logged in reads it; staff change it. Changing it keeps
    attendance in step (see holidaylist.services)."""
    queryset = Holiday.objects.select_related('created_by', 'edited_by')
    serializer_class = HolidaySerializer
    permission_classes = [HolidayPermission]
    filterset_class = HolidayFilter
    search_fields = ['name', 'notes']

    @transaction.atomic
    def perform_create(self, serializer):
        holiday = serializer.save(created_by=self.request.user, edited_by=self.request.user)
        services.apply_to_attendance(holiday)

    @transaction.atomic
    def perform_update(self, serializer):
        old_date = serializer.instance.date
        holiday = serializer.save(edited_by=self.request.user)
        if holiday.date != old_date:
            services.remove_from_attendance(old_date)
        services.apply_to_attendance(holiday)

    @transaction.atomic
    def perform_destroy(self, instance):
        day = instance.date
        instance.delete()
        services.remove_from_attendance(day)

    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """The next few holidays from today (today included): the list for a dashboard or a banner."""
        try:
            count = min(max(int(request.query_params.get('count', 5)), 1), 50)
        except ValueError:
            count = 5
        rows = Holiday.objects.filter(date__gte=date_type.today()).order_by('date')[:count]
        return Response(HolidaySerializer(rows, many=True, context=self.get_serializer_context()).data)
