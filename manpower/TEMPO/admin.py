from django.contrib import admin
from .models import Shift, Activity, ShiftPerson, TimeMaster,Machine


class ActivityTabular(admin.TabularInline):
    model = Activity


class PersonTabular(admin.TabularInline):
    model = ShiftPerson


class ShiftAdmin(admin.ModelAdmin):
    inlines = [ActivityTabular, PersonTabular]

    class Meta:
        model = Shift


admin.site.register(Shift, ShiftAdmin)
admin.site.register(TimeMaster)
admin.site.register(Machine)
