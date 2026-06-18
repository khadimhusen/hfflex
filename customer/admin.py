from django.contrib import admin
from .models import Customer, Address, Person
from myproject.admin_mixins import AutocompleteMixin

class AddressTabular(admin.TabularInline):
    model = Address


class CustomerAdmin(AutocompleteMixin,admin.ModelAdmin):
    search_fields = ['name', 'gst']
    inlines = [AddressTabular]
    class Meta:
        model = Customer


admin.site.register(Customer, CustomerAdmin)
admin.site.register(Address)
admin.site.register(Person)

