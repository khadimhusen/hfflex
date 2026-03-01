from django import forms
from django.forms import modelformset_factory

from order.models import Job, JobMaterial
from purchase.models import Po
from quality.models import QCTest
from .models import (Stockdetail, Inward, ProdReport, ProdInput, JobMaterialStatus,
                     DispatchRegister, ProdPerson, ProdProblem, JobQc, ProblemTag,ProductionProblem)
from customer.models import Customer, Address
from employee.models import Worker
from crispy_forms.helper import FormHelper
from django.forms.widgets import CheckboxSelectMultiple


class InwardForm(forms.ModelForm):
    docdate = forms.DateTimeField(input_formats=('%d/%m/%Y %H:%M',))
    inwarddate = forms.DateTimeField(input_formats=('%d/%m/%Y %H:%M',))

    def __init__(self, *args, **kwargs):
        super(InwardForm, self).__init__(*args, **kwargs)

        self.fields['supplier'].queryset = Customer.objects.filter(is_supplier=True)

    class Meta:
        model = Inward
        fields = ['docdate', 'supplier', 'inwarddate']


class InwardMaterialForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(InwardMaterialForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False

    class Meta:
        model = Stockdetail
        fields = "__all__"


class ProdReportForm(forms.ModelForm):
    processdate = forms.DateTimeField(input_formats=('%d/%m/%Y %H:%M',))

    class Meta:
        model = ProdReport
        fields = "__all__"  # ['docdate', 'supplier', 'inwarddate']
        exclude = ['prodprocess']


class NewProdReportForm(forms.ModelForm):
    processdate = forms.DateTimeField(input_formats=('%d/%m/%Y %H:%M',))

    class Meta:
        model = ProdReport
        fields = ["processdate","qty","unit","totalkg"]


class ProdOutputForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(ProdOutputForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False
        # self.fields['gross_wt'].required = True
        # self.fields['tare_wt'].required = True

    class Meta:
        model = Stockdetail
        fields = "__all__"


class ProdOutputAddForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(ProdOutputAddForm, self).__init__(*args, **kwargs)
        self.fields['gross_wt'].required = True
        self.fields['tare_wt'].required = True

    class Meta:
        model = Stockdetail
        fields = "__all__"


class ProdInputForm(forms.ModelForm):
    inputqty = forms.FloatField(
        widget=forms.TextInput(attrs={'onBlur': "javascript:{this.value=(eval(this.value)).toFixed(3);}"}))

    class Meta:
        model = ProdInput
        fields = "__all__"

    def __init__(self, prodreport=None, createdby=None, *args, **kwargs):
        super(ProdInputForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False
        self.fields['prodreport'] = prodreport
        a = JobMaterialStatus.objects.filter(jobmaterial__job=prodreport.prodprocess.job).values_list('allote_id',
                                                                                                      flat=True)
        b = prodreport.prodprocess.job.jobprocess.all().values_list('id', flat=True)
        c = ProdReport.objects.filter(prodprocess__id__in=b).values_list('id', flat=True)
        self.fields['material'].queryset = Stockdetail.objects.filter(
            id__in=a, balance__gt=0) | Stockdetail.objects.filter(prodreports__in=c, balance__gt=0).order_by(
            'materialname', 'size')

        if 'material' in self.data:
            try:
                self.fields['materail'].queryset = Stockdetail.objects.filter(
                    id__in=a, balance__gt=0) | Stockdetail.objects.filter(prodreports__in=c, balance__gt=0).order_by(
                    'materialname', 'size')

            except (ValueError, TypeError):
                pass  # invalid input from the client; ignore and fallback to empty City queryset
        elif self.instance.pk:
            inputmaterail = self.instance.material_id
            self.fields['material'].queryset = Stockdetail.objects.filter(
                id=inputmaterail) | Stockdetail.objects.filter(
                id__in=a, balance__gt=0) | Stockdetail.objects.filter(prodreports__in=c, balance__gt=0).order_by(
                'materialname', 'size')


class ProdInputEditForm(forms.ModelForm):
    class Meta:
        model = ProdInput
        fields = ['grossinput', 'returned', 'inputqty']

    def __init__(self, *args, **kwargs):
        super(ProdInputEditForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False


class ProdInputBlankForm(forms.ModelForm):
    grossinput = forms.DecimalField(widget=forms.NumberInput(attrs={'onChange': "calculateinputqty()"}))
    returned = forms.DecimalField(widget=forms.NumberInput(attrs={'onChange': "calculateinputqty()"}))

    class Meta:
        model = ProdInput
        fields = ['material', 'grossinput', 'returned', 'inputqty']

    def __init__(self, *args, **kwargs):
        prodreport = kwargs.pop('prodreport')

        super(ProdInputBlankForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False
        a = JobMaterialStatus.objects.filter(jobmaterial__job=prodreport.prodprocess.job).values_list('allote_id',
                                                                                                      flat=True)
        b = prodreport.prodprocess.job.jobprocess.all().values_list('id', flat=True)
        c = ProdReport.objects.filter(prodprocess__id__in=b).values_list('id', flat=True)
        if prodreport.prodprocess.process.process == 'Printing':
            self.fields['material'].queryset = Stockdetail.objects.filter(id__in=a, balance__gt=0, qc_status="Ok"
                                                                          ) | Stockdetail.objects.filter(
                prodreports__in=c, balance__gt=0,
                qc_status="Ok").order_by('materialname', 'size'
                                         ) | Stockdetail.objects.filter(balance__gt=0, qc_status="Ok",
                                                                        materialname__name='TOLUENE'
                                                                        )[:1] | Stockdetail.objects.filter(
                balance__gt=0, qc_status="Ok",
                materialname__name='ETHYL')[:1]
        elif prodreport.prodprocess.process.process == 'Lamination':
            self.fields['material'].queryset = Stockdetail.objects.filter(id__in=a, balance__gt=0, qc_status="Ok"
                                                                          ) | Stockdetail.objects.filter(
                prodreports__in=c, balance__gt=0,
                qc_status="Ok").order_by('materialname', 'size'
                                         ) | Stockdetail.objects.filter(balance__gt=0, qc_status="Ok",
                                                                        materialname__name='ETHYL')[:1]
        elif prodreport.prodprocess.process.process == 'Slitting':
            self.fields['material'].queryset = Stockdetail.objects.filter(id__in=a, balance__gt=0, qc_status="Ok"
                                                                          ) | Stockdetail.objects.filter(
                prodreports__in=c, balance__gt=0,
                qc_status="Ok").order_by('materialname', 'size'
                                         ) | Stockdetail.objects.filter(balance__gt=0, qc_status="Ok",
                                                                        materialname__name='PACKING')[:1]
        elif prodreport.prodprocess.process.process == 'Pouching':
            self.fields['material'].queryset = Stockdetail.objects.filter(id__in=a, balance__gt=0, qc_status="Ok"
                                                                          ) | Stockdetail.objects.filter(
                prodreports__in=c, balance__gt=0,
                qc_status="Ok").order_by('materialname', 'size'
                                         ) | Stockdetail.objects.filter(balance__gt=0, qc_status="Ok",
                                                                        materialname__name='PACKING')[:1]

        else:
            self.fields['material'].queryset = Stockdetail.objects.filter(id__in=a, balance__gt=0, qc_status="Ok"
                                                                          ) | Stockdetail.objects.filter(
                prodreports__in=c, balance__gt=0,
                qc_status="Ok").order_by('materialname', 'size')


class JobMaterialStatusForm(forms.ModelForm):
    qty = forms.DecimalField(
        widget=forms.TextInput(attrs={'onChange': "javascript:{this.value=eval(this.value).toFixed(3)}"}))

    class Meta:
        model = JobMaterialStatus
        fields = ['jobmaterial', 'allote', 'qty']

    def __init__(self, mate=None, sizes=0, mate_type=None, *args, **kwargs):
        super(JobMaterialStatusForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False
        self.fields['allote'].queryset = Stockdetail.objects.filter(materialname=mate, balance__gt=0,
                                                                    item_mat_type=mate_type,
                                                                    size__isnull=True, qc_status="Ok",
                                                                    available__gt=0) | Stockdetail.objects.filter(
            materialname=mate, balance__gt=0, qc_status="Ok",
            size__gte=sizes, item_mat_type=mate_type, available__gt=0).order_by(
            'materialname', 'size', 'micron')

        if 'allote' in self.data:
            try:
                self.fields['allote'].queryset = Stockdetail.objects.filter(
                    materialname=mate, balance__gt=0, size__isnull=True, qc_status="Ok",
                    item_mat_type=mate_type, available__gt=0) | Stockdetail.objects.filter(qc_status="Ok",
                                                                                           materialname=mate,
                                                                                           balance__gt=0,
                                                                                           size__gte=sizes,
                                                                                           item_mat_type=mate_type,
                                                                                           available__gt=0).order_by(
                    'materialname', 'size', 'micron')
            except (ValueError, TypeError):
                pass  # invalid input from the client; ignore and fallback to empty City queryset
        elif self.instance.pk:
            stockdetail_id = self.instance.allote_id
            self.fields['allote'].queryset = Stockdetail.objects.filter(
                materialname=mate, balance__gt=0, item_mat_type=mate_type, qc_status="Ok",
                size__isnull=True, available__gt=0) | Stockdetail.objects.filter(
                id=stockdetail_id) | Stockdetail.objects.filter(
                materialname=mate, balance__gt=0, item_mat_type=mate_type, qc_status="Ok",
                size__gte=sizes, available__gt=0).order_by('materialname', 'size', 'micron')


class DispatchNewForm(forms.ModelForm):
    class Meta:
        model = DispatchRegister
        exclude = ["dispatch_material", "createdby", "editedby"]


class DispatchForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['dispatch_material'].widget = CheckboxSelectMultiple()
        self.fields['dispatch_material'].queryset = Stockdetail.objects.none()
        self.fields['dispatch_material'].label_from_instance = lambda \
                obj: f"{obj.prodreports.all().first().prodprocess.job.rate}/{obj.prodreports.all().first().prodprocess.job.unit}-{obj.prodreports.all().first().prodprocess.job.itemname}= Gross Wt. {obj.gross_wt}"
        self.fields['address'].queryset = Address.objects.none()

        if 'customer' in self.data:
            try:
                customer_id = int(self.data.get('customer'))
                self.fields['address'].queryset = Address.objects.filter(customer_id=customer_id).order_by(
                    'addname')
                self.fields['dispatch_material'].queryset = Stockdetail.objects.filter(
                    prodreports__prodprocess__job__joborder__customer__id=customer_id)

            except (ValueError, TypeError):
                pass  # invalid input from the client; ignore and fallback to empty City queryset
        elif self.instance.pk:
            customer_id = self.instance.customer_id
            self.fields['address'].queryset = self.instance.customer.addresses.order_by('addname')
            self.fields[
                'dispatch_material'].queryset = self.instance.dispatch_material.all() | Stockdetail.objects.filter(
                prodreports__prodprocess__job__joborder__customer__id=customer_id, dispached__isnull=True,
                qc_status="Finished", prodreports__prodprocess__job__dispatch_approval=True,
                prodreports__checked=True, prodreports__approved=True)

    class Meta:
        model = DispatchRegister
        exclude = ["createdby", "editedby", "lock"]


class JobAllotementForm(forms.ModelForm):
    class Meta:
        model = JobMaterialStatus
        fields = ['id', 'jobmaterial', 'qty']


class StockMaterailEditForm(forms.ModelForm):
    class Meta:
        model = Stockdetail
        fields = ['qc_status', 'remark']


class StockMaterailUsedForm(forms.ModelForm):
    class Meta:
        model = ProdInput
        fields = ['inputqty', 'wtgain', 'prodreport']

    def __init__(self, *args, **kwargs):
        super(StockMaterailUsedForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False


class StockMaterailAlloteForm(forms.ModelForm):
    class Meta:
        model = JobMaterialStatus
        fields = ['jobmaterial', 'qty']

        def __init__(self, *args, **kwargs):
            super(StockMaterailAlloteForm, self).__init__(*args, **kwargs)
            self.helper = FormHelper()
            self.helper.form_show_labels = False


class AddPersonForm(forms.ModelForm):
    class Meta:
        model = ProdPerson
        fields = ['person']

    def __init__(self, *args, **kwargs):
        super(AddPersonForm, self).__init__(*args, **kwargs)
        self.fields['person'].queryset = Worker.objects.filter(is_active=True)


class AddProblemForm(forms.ModelForm):
    class Meta:
        model = ProdProblem
        fields = ['problem', "timewaste", 'action']


class DispatchApprovalForm(forms.ModelForm):


    class Meta:
        model = Job
        fields = ['dispatch_approval', 'dispatch_remark','invoice']

    def __init__(self,*args,**kwargs):
        super(DispatchApprovalForm, self).__init__(*args, **kwargs)
        if self.instance.prejob:
            if (self.instance.prejob.new_cyl_qty or 0) > 1  or (self.instance.prejob.design_charges or 0) > 1:
                self.fields['invoice'] = forms.CharField(required=True)
        else:
            self.fields['invoice'] = forms.CharField(required=False)




class Jobmaterialtoroder(forms.ModelForm):
    class Meta:
        model = JobMaterial
        fields = ['orderedqty', 'receivedqty','po']

    def __init__(self, *args, **kwargs):
        super(Jobmaterialtoroder, self).__init__(*args, **kwargs)
        self.fields['po'].queryset = Po.objects.none()

        if 'po' in self.data:
            try:
                self.fields['po'].queryset = Po.objects.filter(id=self.data.get("po")) | Po.objects.filter(
                    status="Pending",approvedby__isnull=True)
            except (ValueError, TypeError):
                pass
        elif self.instance:
            if self.instance.po:
                self.fields['po'].queryset = Po.objects.filter(id=self.instance.po.id) | Po.objects.filter(
                    status="Pending",approvedby__isnull=True)
            else:
                self.fields['po'].queryset = Po.objects.filter(status="Pending",approvedby__isnull=True)


class AddJobQcForm(forms.ModelForm):
    class Meta:
        model=JobQc
        fields=["qctest","result"]

    def __init__(self, *args, **kwargs):
        super(AddJobQcForm, self).__init__(*args, **kwargs)
        insts=kwargs.get('instance')
        if insts:
            reportprocess=kwargs['instance'].prodprocess.process
            self.fields['qctest'].queryset = reportprocess.qctest_set.all()


class ProblemTagForm(forms.ModelForm):
    class Meta:
        model= ProblemTag
        fields= ['tagname']

