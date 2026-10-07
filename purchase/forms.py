from crispy_forms.helper import FormHelper
from django import forms
from .models import Po, PoItem, Term, PoImage,ExpectedDate
from customer.models import Address, Customer
from company.models import Company, default_company
from django.db.models import Q
from django.forms.widgets import CheckboxSelectMultiple


class PoForm(forms.ModelForm):
    delivery_date = forms.DateTimeField(input_formats=('%d/%m/%Y %H:%M',))

    class Meta:
        model = Po
        fields = "__all__"
        exclude = ["approvedby", "createdby", "editedby", "approve_date"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['supplier'].queryset = Customer.objects.filter(active=True, is_supplier=True).order_by('name')
        self.fields["poterm"].widget = CheckboxSelectMultiple()
        self.fields["poterm"].queryset = Term.objects.all()
        # Buyer: one of our active companies, always one of them (no blank
        # entry) -- plus the order's current buyer, so editing an old PO whose
        # company was deactivated since doesn't make its own value invalid.
        # Not required: a post that omits it (a page loaded before this field
        # existed) keeps the model default / the order's existing buyer.
        self.fields['buyer'].queryset = Company.objects.filter(
            Q(is_active=True) | Q(pk=self.instance.buyer_id)).order_by('name')
        self.fields['buyer'].empty_label = None
        self.fields['buyer'].required = False
        # Delivery addresses are the buyer's: the one posted, else the order's
        # own, else the default company's.
        self.fields['delivery_at'].queryset = self.buyer_company().delivery_addresses()

        if 'supplier' in self.data:
            try:
                supplier_id = int(self.data.get('supplier'))
                print("Supplier id : ", supplier_id)
                self.fields['supplier'].queryset = Customer.objects.filter(active=True, is_supplier=True).order_by(
                    'name')
            except (ValueError, TypeError):
                pass  # invalid input from the client; ignore and fallback to empty City queryset


    def buyer_company(self):
        buyer_id = self.data.get('buyer') if self.is_bound else None
        company = None
        if buyer_id and str(buyer_id).isdigit():
            company = Company.objects.filter(pk=int(buyer_id)).first()
        return company or self.instance.buyer or default_company() or Company()

    def clean(self):
        cleaned = super().clean()
        # Ship-to follows the buyer when the page doesn't offer the field (the
        # new-order page) or leaves it empty: the buyer's own customer record.
        if not cleaned.get('ship_to'):
            buyer = cleaned.get('buyer') or self.buyer_company()
            cleaned['ship_to'] = buyer.receiving_customer
        return cleaned


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