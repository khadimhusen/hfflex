from django.contrib import admin
from .models import Document, DocumentDownloadLog


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'uploaded_by', 'created_at')
    list_filter = ('uploaded_by',)
    filter_horizontal = ('viewers',)
    search_fields = ('title', 'description')

@admin.register(DocumentDownloadLog)
class DocumentDownloadLogAdmin(admin.ModelAdmin):
    list_display = ('document', 'downloaded_by', 'downloaded_at', 'ip_address')
    list_filter = ('downloaded_by', 'downloaded_at')
    search_fields = ('document__title', 'downloaded_by__username')
    date_hierarchy = 'downloaded_at'