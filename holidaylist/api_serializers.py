from datetime import date as date_type

from rest_framework import serializers

from .models import Holiday


class HolidaySerializer(serializers.ModelSerializer):
    weekday = serializers.SerializerMethodField()
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)
    days_away = serializers.SerializerMethodField()
    edited_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Holiday
        fields = ['id', 'date', 'weekday', 'name', 'kind', 'kind_display', 'notes', 'days_away',
                  'edited', 'edited_by_name']
        read_only_fields = ['edited']
        # The model's own unique check would answer first with a bland message; validate_date
        # does the same job and names the holiday that is already there.
        extra_kwargs = {'date': {'validators': []}}

    def get_weekday(self, obj):
        return obj.date.strftime('%A')

    def get_days_away(self, obj):
        """0 today, 3 in three days, -2 two days ago."""
        return (obj.date - date_type.today()).days

    def get_edited_by_name(self, obj):
        user = obj.edited_by or obj.created_by
        return (user.get_full_name().strip() or user.username) if user else ''

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Give the holiday a name.')
        return value

    def validate_date(self, value):
        clash = Holiday.objects.filter(date=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        other = clash.first()
        if other is not None:
            raise serializers.ValidationError(f'{value:%d/%m/%Y} is already on the list: {other.name}.')
        return value

    def validate_notes(self, value):
        return value.strip()
