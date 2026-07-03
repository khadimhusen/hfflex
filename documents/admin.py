from django.contrib import admin
from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'uploaded_by', 'created_at')
    list_filter = ('uploaded_by',)
    filter_horizontal = ('viewers',)
    search_fields = ('title', 'description')