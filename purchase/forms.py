from crispy_forms.helper import FormHelper
from django import forms
from .models import Po, PoItem, Term, PoImage,ExpectedDate
from customer.models import Address, Customer
from django.forms.widgets import CheckboxSelectMultiple


class PoForm(forms.ModelForm):
    delivery_date = forms.DateTimeField(input_formats=('%d/%m/%Y %H:%M',))

    class Meta:
        model = Po
        fields = "__all__"
        exclude = ["approvedby", "createdby", "editedby", "approve_date"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['delivery_at'].queryset = Address.objects.filter(customer_id=31)
        self.fields['supplier'].queryset = Customer.objects.filter(active=True, is_supplier=True).order_by('name')
        self.fields["poterm"].widget = CheckboxSelectMultiple()
        self.fields["poterm"].queryset = Term.objects.all()

        if 'supplier' in self.data:
            try:
                supplier_id = int(self.data.get('supplier'))
                print("Supplier id : ", supplier_id)
                self.fields['supplier'].queryset = Customer.objects.filter(active=True, is_supplier=True).order_by(
                    'name')
                self.fields['delivery_at'].queryset = Address.objects.filter(customer_id=31).order_by(
                    'addname')
            except (ValueError, TypeError):
                pass  # invalid input from the client; ignore and fallback to empty City queryset


class PoItemForm(forms.ModelForm):
    rate = forms.DecimalField(
        widget=forms.TextInput(attrs={'onChange': "javascript:{this.value=eval(this.value).toFixed(2)}"}))

    class Meta:
        model = PoItem
        fields = "__all__"
        widgets = {
            "description": forms.Textarea(attrs={'rows':1, 'cols':80,
                'style': 'overflow: hidden',
                'oninput':"this.style.height='auto'; this.style.height=`${this.scrollHeight}px`",
                'onfocus':"this.style.height='auto'; this.style.height=`${this.scrollHeight}px`",
                'list': 'itemlist'
                })
        }

    def __init__(self, *args, **kwargs):
        super(PoItemForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False


class PoItemFormMarketing(forms.ModelForm):

    class Meta:
        model = PoItem

        exclude = ["rate"]
        widgets = {
            "description": forms.Textarea(attrs={'rows':1, 'cols':80,
                'style': 'overflow: hidden',
                'oninput':"this.style.height='auto'; this.style.height=`${this.scrollHeight}px`",
                'onfocus':"this.style.height='auto'; this.style.height=`${this.scrollHeight}px`",
                'list': 'itemlist'
                })
        }

    def __init__(self, *args, **kwargs):
        super(PoItemFormMarketing, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False



class PoApprovalForm(forms.ModelForm):
    class Meta:
        model = Po
        fields = ["approvedby", "approve_date"]


class PoImageForm(forms.ModelForm):
    class Meta:
        model = PoImage
        exclude = ["createdby", "editedby", "po"]


class ExpectedDateForm(forms.ModelForm):
    expected_date = forms.DateField(input_formats=('%d/%m/%Y',))

    class Meta:
        model = ExpectedDate
        fields=["expected_date","remark"]