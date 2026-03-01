from django import forms
from .models import *
from crispy_forms.helper import FormHelper


class CustomerForm(forms.ModelForm):
    name = forms.CharField(
        widget=forms.TextInput(attrs={'onBlur': "javascript:{this.value = this.value.toUpperCase();}"}))

    class Meta:
        model = Customer
        fields = ['name', 'gst', 'is_customer', 'is_supplier', 'active', 'email']


class AddressForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(AddressForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False

    class Meta:
        model = Address
        fields = ['addname', 'add1', 'add2', 'pincode', 'phone', 'remark']


class PersonForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(PersonForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False

    class Meta:
        model = Person
        fields = ['name', 'designation', 'mobile', 'email', 'remark']
