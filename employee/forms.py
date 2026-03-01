from django import forms
from .models import Access
from crispy_forms.helper import FormHelper




class AccessFrom(forms.ModelForm):

    class Meta:
        model = Access
        fields = ['viewname']

    def __init__(self, *args, **kwargs):
        super(AccessFrom, self).__init__(*args, **kwargs)
        self.helper=FormHelper()
        self.helper.form_show_labels=False
        
