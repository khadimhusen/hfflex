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
        
