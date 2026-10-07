from django.contrib import admin

from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_name', 'gstin', 'is_default', 'is_active')
    list_filter = ('is_active', 'is_default')
    search_fields = ('name', 'short_name', 'gstin')
    autocomplete_fields = ('customer',)
    readonly_fields = ('created', 'createdby', 'edited', 'editedby')
    fieldsets = (
        (None, {'fields': ('name', 'short_name', 'gstin', 'customer', 'is_default', 'is_active')}),
        ('Letterhead', {'fields': ('logo', 'address_line1', 'address_line2', 'phone', 'email', 'website')}),
        ('Record', {'fields': ('created', 'createdby', 'edited', 'editedby')}),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.createdby = request.user
        obj.editedby = request.user
        super().save_model(request, obj, form, change)
