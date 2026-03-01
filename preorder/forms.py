from django import forms
from .models import PreOrder, JobName


class AddPreOrderForm(forms.ModelForm):
    customer = forms.CharField(widget=forms.TextInput(attrs={'list': 'customerlist'}))
    gst = forms.CharField(widget=forms.TextInput(attrs={'pattern':"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$|URP|As Per Master",
                                                        'title':"Invalid GST Number Or Type 'URP' for no GST Or Type 'As Per Master'. "}))

    class Meta:
        model = PreOrder
        fields = ["customer",
                  "address",
                  "contact_number",
                  "schedule",
                  "gst"
                  ]
