from django.contrib import admin

from . import services
from .models import Holiday


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('date', 'name', 'kind', 'notes')
    list_filter = ('kind',)
    search_fields = ('name', 'notes')
    date_hierarchy = 'date'

    # Keep attendance in step when the list is changed here, as it is from the screens.
    def save_model(self, request, obj, form, change):
        old_date = Holiday.objects.get(pk=obj.pk).date if change else None
        super().save_model(request, obj, form, change)
        if old_date and old_date != obj.date:
            services.remove_from_attendance(old_date)
        services.apply_to_attendance(obj)

    def delete_model(self, request, obj):
        day = obj.date
        super().delete_model(request, obj)
        services.remove_from_attendance(day)
