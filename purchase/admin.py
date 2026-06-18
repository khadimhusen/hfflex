from django.contrib import admin
from .models import Term, Po, PoItem, PoImage

@admin.register(Po)  # check exact model name
class PurchaseOrderAdmin(admin.ModelAdmin):
    search_fields = ['id']



admin.site.register(Term)

admin.site.register(PoItem)
admin.site.register(PoImage)