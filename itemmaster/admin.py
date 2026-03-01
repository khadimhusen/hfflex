from django.contrib import admin
from .models import ItemMaster, RawMaterial, PouchType, LamiRubber, ItemImage, ItemProcess, Process, CylinderMovement
from .models import Color, ItemColor, Problem, Machine, AttributeMaster, ItemAttribute


class RawMaterialTabular(admin.TabularInline):
    model = RawMaterial


class ItemProcessAdmin(admin.ModelAdmin):
    list_display = ['process']
    ordering = ['process']


class ItemProcessTabular(admin.TabularInline):
    model = ItemProcess

class ItemImage(admin.TabularInline):
    model = ItemImage


class ItemMasterAdmin(admin.ModelAdmin):
    inlines = [ItemImage, RawMaterialTabular, ItemProcessTabular]

    class Meta:
        model = ItemMaster


admin.site.register(ItemMaster, ItemMasterAdmin)
admin.site.register(RawMaterial)
admin.site.register(PouchType)
admin.site.register(LamiRubber)
admin.site.register(ItemProcess, ItemProcessAdmin)
admin.site.register(Process)
admin.site.register(Color)
admin.site.register(ItemColor)
admin.site.register(Problem)
admin.site.register(Machine)
admin.site.register(AttributeMaster)
admin.site.register(ItemAttribute)
admin.site.register(CylinderMovement)
