from django.contrib import admin
from .models import ItemMaster, RawMaterial, PouchType, LamiRubber, ItemImage, ItemProcess, Process, CylinderMovement
from .models import ( Color, ItemColor, Problem, Machine, AttributeMaster,
                      ItemAttribute, ItemStandardParameter, StdParameter, MachineTask)
from myproject.admin_mixins import AutocompleteMixin

class RawMaterialTabular(admin.TabularInline):
    model = RawMaterial


@admin.register(Process)
class ProcessAdmin(AutocompleteMixin,admin.ModelAdmin):
    search_fields = ['process']
    list_display = ['process']
    ordering = ['process']


class ItemProcessTabular(admin.TabularInline):
    model = ItemProcess

class ItemImage(admin.TabularInline):
    model = ItemImage


@admin.register(MachineTask)  # check which app has Color model
class MachineTaskAdmin(AutocompleteMixin,admin.ModelAdmin):
    search_fields = [ 'task','machine__machinename']


@admin.register(Color)  # check which app has Color model
class ColorAdmin(AutocompleteMixin,admin.ModelAdmin):
    search_fields = ['colorname', 'pantonecolor']


class ItemMasterAdmin(AutocompleteMixin,admin.ModelAdmin):
    search_fields = ['name', 'id']
    inlines = [ItemImage, RawMaterialTabular, ItemProcessTabular]

    class Meta:
        model = ItemMaster


admin.site.register(ItemMaster, ItemMasterAdmin)
admin.site.register(RawMaterial)
admin.site.register(PouchType)
admin.site.register(LamiRubber)
admin.site.register(ItemProcess)


admin.site.register(ItemColor)
admin.site.register(Problem)
admin.site.register(Machine)
admin.site.register(AttributeMaster)
admin.site.register(ItemAttribute)
admin.site.register(CylinderMovement)
admin.site.register(StdParameter)
admin.site.register(ItemStandardParameter)

