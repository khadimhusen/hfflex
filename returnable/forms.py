from crispy_forms.helper import FormHelper
from django import forms
from .models import Returnable, ChallanItem, ReceivedChallan, ReceivedItem
from customer.models import Address, Customer


class ReturnableForm(forms.ModelForm):
    dispatch_date = forms.DateTimeField(input_formats=('%d/%m/%Y %H:%M',))
    expected_date = forms.DateTimeField(input_formats=('%d/%m/%Y %H:%M',))

    class Meta:
        model = Returnable
        fields = "__all__"
        exclude = ["createdby", "editedby"]
        widgets = {
            "remark": forms.Textarea(attrs={'rows': 3, 'cols': 80})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['address'].queryset = Address.objects.none()
        self.fields['party_name'].queryset = Customer.objects.filter(active=True, is_supplier=True).order_by('name')

        if 'party_name' in self.data:
            try:
                party_name_id = int(self.data.get('party_name'))
                print("party_name id : ", party_name_id)
                self.fields['party_name'].queryset = Customer.objects.filter(active=True, is_supplier=True).order_by(
                    'name')
                self.fields['address'].queryset = Address.objects.filter(customer_id=party_name_id).order_by(
                    'addname')
            except (ValueError, TypeError):
                pass  # invalid input from the client; ignore and fallback to empty City queryset

        elif self.instance.pk:
            party_name_id = self.instance.party_name_id
            self.fields['address'].queryset = self.instance.party_name.addresses.order_by('addname')
            self.fields['party_name'].queryset = Customer.objects.filter(id=party_name_id)


class ChallanItemForm(forms.ModelForm):
    class Meta:
        model = ChallanItem
        fields = "__all__"
        widgets = {
            "description": forms.Textarea(attrs={'rows': 1, 'cols': 80,
                                                 'style': 'overflow: hidden',
                                                 'oninput': "this.style.height='auto'; this.style.height=`${this.scrollHeight}px`",
                                                 'onfocus': "this.style.height='auto'; this.style.height=`${this.scrollHeight}px`",
                                                 'list': 'itemlist'
                                                 })
        }

    def __init__(self, *args, **kwargs):
        super(ChallanItemForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False


class ReceivedChallanForm(forms.ModelForm):


    class Meta:
        model = ReceivedChallan
        fields = "__all__"
        exclude = ["createdby", "editedby"]
        widgets = {
            "remark": forms.Textarea(attrs={'rows': 3, 'cols': 80})}


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['party_name'].queryset = Customer.objects.filter(active=True, is_supplier=True).order_by('name')


class ReceivedItemForm(forms.ModelForm):
    class Meta:
        model = ReceivedItem
        fields = "__all__"
        exclude = ["createdby", "editedby"]

    def __init__(self, *args, **kwargs):
        self.rc_instance = kwargs.pop('rc_instance', None)
        super().__init__(*args, **kwargs)

        if self.rc_instance:
            # Items matching party + status filter
            filtered_qs = ChallanItem.objects.filter(
                returnable__party_name=self.rc_instance.party_name,
                returnable__status__in=["Dispatched", "Delivered", "Partially received"]
            ).select_related('returnable')

            # Items already saved in this ReceivedChallan (preserve existing selections)
            existing_qs = ChallanItem.objects.filter(
                receiveditem__received_challan=self.rc_instance
            ).select_related('returnable')

            self.fields['received_item'].queryset = (filtered_qs | existing_qs).distinct()
        else:
            self.fields['received_item'].queryset = ChallanItem.objects.none()

