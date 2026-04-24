from django.contrib import admin
from django_ckeditor_5.widgets import CKEditor5Widget
from django import forms
from .models import Resolution, ResolutionDocument, ResolutionEditor


class ResolutionAdminForm(forms.ModelForm):
    class Meta:
        model = Resolution
        fields = '__all__'
        widgets = {
            'content': CKEditor5Widget(config_name='default', attrs={'class': 'django_ckeditor_5'}),
        }


class DocumentInline(admin.TabularInline):
    model = ResolutionDocument
    extra = 1


@admin.register(Resolution)
class ResolutionAdmin(admin.ModelAdmin):
    form = ResolutionAdminForm
    list_display = ['resolution_number', 'title', 'meeting_date', 'meeting_type', 'status', 'created_by']
    list_filter = ['status', 'meeting_type', 'meeting_date']
    search_fields = ['resolution_number', 'title']
    inlines = [DocumentInline]
    readonly_fields = ['created_by', 'created_at', 'updated_at', 'published_at']

    class Media:
        css = {
            'all': ('resolutions/admin_resolution.css',)
        }

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)