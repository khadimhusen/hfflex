from django import forms
from django.forms import CheckboxSelectMultiple

from .models import Quotation, QuotationItem, Term


class QuotationForm(forms.ModelForm):
    quotedate = forms.DateField(input_formats=('%d/%m/%Y',))

    class Meta:
        model= Quotation
        fields = "__all__"
        exclude = ["approvedby", "createdby", "editedby", "approved","status"]

    def __init__(self,*args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["quote_term"].widget = CheckboxSelectMultiple()
        self.fields["quote_term"].queryset = Term.objects.all()

class QuoteItemForm(forms.ModelForm):

    class Meta:
        model=QuotationItem
        fields = "__all__"


class QuoteApprovalForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = ["approvedby", "approved"]
