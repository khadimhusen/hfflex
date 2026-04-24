from django import forms
from django.forms import inlineformset_factory
from django_ckeditor_5.widgets import CKEditor5Widget
from .models import Resolution, ResolutionDocument


class ResolutionForm(forms.ModelForm):
    class Meta:
        model = Resolution
        fields = [
            'resolution_number', 'title', 'content',
            'meeting_date', 'meeting_location', 'meeting_type', 'status',
        ]
        widgets = {
            'content': CKEditor5Widget(config_name='default', attrs={'class': 'django_ckeditor_5'}),
            'meeting_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'resolution_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. RES-2024-001'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'meeting_location': forms.TextInput(attrs={'class': 'form-control'}),
            'meeting_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class ResolutionDocumentForm(forms.ModelForm):
    class Meta:
        model = ResolutionDocument
        fields = ['name', 'file']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Document name'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
        }


# Inline formset — attach multiple documents to one resolution
DocumentFormSet = inlineformset_factory(
    Resolution,
    ResolutionDocument,
    form=ResolutionDocumentForm,
    extra=2,
    can_delete=True,
)