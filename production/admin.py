from django.contrib import admin
from .models import (Inward, Stockdetail, ProdReport, ProdInput, ProdPerson, JobMaterialStatus,
                     DispatchRegister, OtherDispatchItem, JobQc, ProblemTag, ProductionProblem)


class MaterialdetailAdmin(admin.ModelAdmin):
    list_display = ('packing', 'gross_wt', 'tare_wt', 'net_wt', 'nos')

    list_editable = ( 'gross_wt', 'tare_wt', 'net_wt', 'nos')

class StockdetailAdmin(admin.ModelAdmin):
    list_display = ('materialname', 'item_mat_type','item_grade', 'size',
                    'micron', 'qc_status', 'recieved','available','alloted',
                    'balance', 'content_type', 'object_id')
    list_editable = ( 'qc_status', 'recieved','available','alloted',
                    'balance', 'content_type', 'object_id')
    ordering = ['materialname', 'balance']
    list_filter = ('qc_status','materialname', 'item_mat_type','item_grade','available','balance', )



admin.site.register(Inward)
admin.site.register(Stockdetail,StockdetailAdmin )
admin.site.register(ProdReport)
admin.site.register(ProdInput)
admin.site.register(ProdPerson)
admin.site.register(JobMaterialStatus)
admin.site.register(DispatchRegister)
admin.site.register(OtherDispatchItem)
admin.site.register(JobQc)
admin.site.register(ProblemTag)
admin.site.register(ProductionProblem)


