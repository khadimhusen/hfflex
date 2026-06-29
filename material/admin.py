from django.contrib import admin
from .models import Material, MatType, Grade, Unit, Commodity, PurchaseMaterial


class MaterialAdmin(admin.ModelAdmin):
    search_fields = ['name']
    list_display = ('name', 'density', 'solid', 'weightgain', 'state')
    list_editable = ('density', 'solid', 'weightgain', 'state')
    ordering = ['id']


class MatTypeAdmin(admin.ModelAdmin):
    list_display = ('mat_type',)
    ordering = ['id']


class GradeAdmin(admin.ModelAdmin):
    list_display = ('grade',)
    ordering = ['id']


class UnitAdmin(admin.ModelAdmin):
    search_fields = ['unit']
    list_display = ('unit',)
    ordering = ['id']


admin.site.register(Material, MaterialAdmin)
admin.site.register(MatType, MatTypeAdmin)
admin.site.register(Grade, GradeAdmin)
admin.site.register(Unit, UnitAdmin)
admin.site.register(Commodity)
admin.site.register(PurchaseMaterial)
