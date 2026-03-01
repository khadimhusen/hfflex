from django.contrib import admin
from .models import Term, Quotation, QuotationItem, MaterialRate, AdditionTerm,NewRate,PreDefinedMaterial,MaterialStructure

class RateDetail(admin.ModelAdmin):
    list_display = ('id', 'material', 'density', 'rate', 'created', 'edited')


# Register your models here.
admin.site.register(Term)
admin.site.register(MaterialRate, RateDetail)
admin.site.register(Quotation)
admin.site.register(QuotationItem)
admin.site.register(AdditionTerm)
admin.site.register(NewRate)
admin.site.register(PreDefinedMaterial)
admin.site.register(MaterialStructure)
