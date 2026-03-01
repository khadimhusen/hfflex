from django.contrib import admin
from .models import Customer, Address, Person

class AddressTabular(admin.TabularInline):
    model = Address


class CustomerAdmin(admin.ModelAdmin):
    inlines = [AddressTabular]
    class Meta:
        model = Customer


admin.site.register(Customer, CustomerAdmin)
admin.site.register(Address)
admin.site.register(Person)
