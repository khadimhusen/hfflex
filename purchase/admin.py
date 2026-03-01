from django.contrib import admin
from .models import Term, Po, PoItem, PoImage


admin.site.register(Term)
admin.site.register(Po)
admin.site.register(PoItem)
admin.site.register(PoImage)