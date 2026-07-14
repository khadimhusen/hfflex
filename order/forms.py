from django import forms
from .models import *
from customer.models import Address
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column
from itemmaster.models import ItemMaster, Customer
from django.contrib.auth.models import User
from employee.models import Department


class OrderForm(forms.ModelForm):
    podate = forms.DateTimeField(input_formats=('%d/%m/%Y %H:%M',))
    deliverydate = forms.DateTimeField(input_formats=('%d/%m/%Y %H:%M',))
    marketing_person = forms.ModelChoiceField(
        queryset=User.objects.filter(
            department__department_name='marketing',
            is_active=True
        ),
        required=False
    )

    class Meta:
        model = Order
        fields = ['customer', 'po', 'podate', 'deliverydate',
                  'paymentterms', 'tax1', 'tax2', 'transport',
                  'remark', 'delivery_at', 'status']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['delivery_at'].queryset = Address.objects.none()
        self.fields['customer'].queryset = Customer.objects.filter(active=True).order_by('name')

        if 'customer' in self.data:
            try:
                customer_id = int(self.data.get('customer'))
                self.fields['customer'].queryset = Customer.objects.filter(active=True).order_by('name')
                self.fields['delivery_at'].queryset = Address.objects.filter(customer_id=customer_id).order_by(
                    'addname')
            except (ValueError, TypeError):
                pass  # invalid input from the client; ignore and fallback to empty City queryset
        elif self.instance.pk:
            self.fields['delivery_at'].queryset = self.instance.customer.addresses.order_by('addname')



class JobForm(forms.ModelForm):
    class Meta:
        model = Job
        fields = ['prejob', 'createdby', 'itemmaster', 'quantity', 'unit', 'rate', 'waste', 'jobremark']

    def __init__(self, customerid=None, createdby=None, *args, **kwargs):
        super(JobForm, self).__init__(*args, **kwargs)
        self.customerid = customerid
        self.fields['createdby'].field = createdby
        self.fields['itemmaster'].queryset = ItemMaster.objects.filter(itemcustomer_id=customerid,
                                                                       active=True).order_by('itemname')
        self.fields['prejob'].queryset = JobName.objects.filter(job__isnull=True,preorder__final_submition=True)
        self.helper = FormHelper()
        self.helper.form_show_labels = False

        if 'itemmaster' in self.data:
            try:
                self.fields['itemmaster'].queryset = ItemMaster.objects.filter(itemcustomer_id=customerid,
                                                                               active=True).order_by(
                    'itemname') | ItemMaster.objects.filter(id=self.data.get("itemmaster"))
                self.fields['prejob'].queryset = JobName.objects.filter(job__isnull=True,preorder__final_submition=True) | JobName.objects.filter(
                    id=self.data.get("prejob"))
            except (ValueError, TypeError):
                pass  # invalid input from the client; ignore and fallback to empty City queryset
        elif self.instance.pk:
            itemmaster = self.instance.itemmaster.id

            self.fields['itemmaster'].queryset = ItemMaster.objects.filter(itemcustomer_id=customerid,
                                                                           active=True).order_by(
                'itemname') | ItemMaster.objects.filter(id=itemmaster)
            if self.instance.prejob:
                self.fields['prejob'].queryset = JobName.objects.filter(job__isnull=True,preorder__final_submition=True)|\
                                                 JobName.objects.filter(id=self.instance.prejob.id)
            else:
                self.fields['prejob'].queryset = JobName.objects.filter(job__isnull=True,preorder__final_submition=True)


class JobFormdetail(forms.ModelForm):
    class Meta:
        model = Job
        fields = ['itemmaster', 'quantity', 'unit', 'rate', 'waste', 'jobstatus', 'jobremark']

    def __init__(self, *args, **kwargs):
        super(JobFormdetail, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False


class JobMaterialForm(forms.ModelForm):
    class Meta:
        model = JobMaterial
        fields = ['materialname', 'item_mat_type', 'item_grade', 'size', 'micron', 'gsm',
                  'req', 'available', 'to_order', ]

    def __init__(self, *args, **kwargs):
        super(JobMaterialForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('materialname', css_class='form-group col-md-3 mb-0'),
                Column('item_mat_type', css_class='form-group col-md-1 mb-0'),
                Column('item_grade', css_class='form-group col-md-1 mb-0'),
                Column('size', css_class='form-group col-md-1 mb-0'),
                Column('micron', css_class='form-group col-md-1 mb-0'),
                Column('gsm', css_class='form-group col-md-1 mb-0'),
                Column('req', css_class='form-group col-md-3 mb-0'),
                css_class='form-row'),
        )
        self.helper.form_show_labels = False


class JobDetailEditForm(forms.ModelForm):
    class Meta:
        model = Job
        exclude = ['joborder', 'itemmaster','prejob','approvedby','account_clearance_date']


class JobProcessForm(forms.ModelForm):
    class Meta:
        model = JobProcess
        exclude = ["process_count"]

    def __init__(self, *args, **kwargs):
        super(JobProcessForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False


class JobImageForm(forms.ModelForm):
    class Meta:
        model = JobImage
        fields = ["imagename"]


class JobItemAttributeForm(forms.ModelForm):
    class Meta:
        model = JobItemAttribute
        fields = ['item_attirbuate','attri_value']


class JobCoaForm(forms.ModelForm):
    class Meta:
        model = JobCoa
        fields = ["standard_parameter", "value"]

    def __init__(self, *args, **kwargs):
        super(JobCoaForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False

class JobColorForm(forms.ModelForm):
    class Meta:
        model = JobColor
        fields = ["color", "remark"]

    def __init__(self, *args, **kwargs):
        super(JobColorForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False

# ------------


class AssignMarketingPersonForm(forms.Form):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all().order_by('name'),
        label='Customer',
        empty_label='— Select Customer —',
    )
    marketing_person = forms.ModelChoiceField(
        queryset=User.objects.filter(
            id__in=Department.objects.filter(
                department_name='marketing'
            ).values_list('user__id', flat=True),
            is_active=True,
        ).order_by('first_name', 'last_name'),
        label='Marketing Person',
        empty_label='— Select Marketing Person —',
    )