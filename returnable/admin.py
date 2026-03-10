from django.contrib import admin
from .models import Returnable, ReceivedChallan, ReceivedItem, ChallanItem


admin.site.register(Returnable)
admin.site.register(ReceivedChallan)
admin.site.register(ReceivedItem)
admin.site.register(ChallanItem)