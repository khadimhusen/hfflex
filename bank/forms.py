from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit
from django import forms

from bank.models import Cheque


class ChequeCreationForm(forms.ModelForm):
    startnum = forms.IntegerField()
    endnum = forms.IntegerField()

    class Meta:
        model = Cheque
        fields = ['bank']


class ChequeEditForm(forms.ModelForm):
    party = forms.CharField(widget=forms.TextInput(attrs={'list': 'partylist'}))

    class Meta:
        model = Cheque
        fields = ["party", "cheque_date", "amount", "status", "expected_date", "bill_number",
                  "bill_date", "remark"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('party', css_class='form-group col-md-6 mb-0'),
                Column('cheque_date', css_class='form-group col-md-3 mb-0'),
                Column('amount', css_class='form-group col-md-3 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('status', css_class='form-group col-md-3 mb-0'),
                Column('expected_date', css_class='form-group col-md-3 mb-0'),
                Column('bill_number', css_class='form-group col-md-3 mb-0'),
                Column('bill_date', css_class='form-group col-md-3 mb-0'),
                css_class='form-row'
            ),
            "remark",
            Submit('submit', 'Save Form Detail')
        )