from django import forms
from django.contrib.auth.models import User
from .models import Document


class DocumentUploadForm(forms.ModelForm):
    viewers = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Document
        fields = ['title', 'description', 'file', 'viewers']

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # exclude the uploader from the viewer-selection list — they already have access
        qs = User.objects.filter(is_active=True)
        if user:
            qs = qs.exclude(pk=user.pk)
        self.fields['viewers'].queryset = qs.order_by('first_name', 'username')


class ManageViewersForm(forms.ModelForm):
    viewers = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Document
        fields = ['viewers']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        qs = User.objects.filter(is_active=True)
        if instance:
            qs = qs.exclude(pk=instance.uploaded_by_id)
        self.fields['viewers'].queryset = qs.order_by('first_name', 'username')