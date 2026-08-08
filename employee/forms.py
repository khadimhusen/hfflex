from django import forms
from .models import Access
from crispy_forms.helper import FormHelper

from django.contrib.auth.models import User

class CopyDepartmentForm(forms.Form):
    source_user = forms.ModelChoiceField(
        queryset=User.objects.all().order_by('username'),
        label="Copy departments FROM this user",
        help_text="All departments of this user will be copied to the selected users."
    )
    replace = forms.BooleanField(
        required=False,
        label="Replace existing departments",
        help_text="If checked, target user's current departments are cleared first."
    )




class AccessFrom(forms.ModelForm):

    class Meta:
        model = Access
        fields = ['viewname']

    def __init__(self, *args, **kwargs):
        super(AccessFrom, self).__init__(*args, **kwargs)
        self.helper=FormHelper()
        self.helper.form_show_labels=False
        
from django import forms
from django.core.exceptions import ValidationError
from .models import CompanyAsset, AssetAssignment


class CompanyAssetForm(forms.ModelForm):
    class Meta:
        model = CompanyAsset
        fields = ['name', 'cost', 'description', 'date_of_purchase']



class AssetIssueForm(forms.ModelForm):
    class Meta:
        model = AssetAssignment
        fields = ['asset', 'employee', 'issuing_date']
        widgets = {
            'issuing_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['asset'].queryset = CompanyAsset.objects.filter(is_active=True)


class AssetReturnForm(forms.ModelForm):
    class Meta:
        model = AssetAssignment
        fields = ['return_date']
        widgets = {
            'return_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        }


class AssetDisposeForm(forms.ModelForm):
    class Meta:
        model = CompanyAsset
        fields = ['disposal_date', 'disposal_reason']
        widgets = {
            'disposal_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.is_active = False
        if commit:
            instance.full_clean()
            instance.save()
        return instance