# coa/forms.py
from django import forms
from django.forms import inlineformset_factory
from crispy_forms.helper import FormHelper

from order.models import JobCoa
from .models import Coa, TestParameter
from itemmaster.models import StdParameter, ItemStandardParameter


class CoaForm(forms.ModelForm):
    class Meta:
        model = Coa
        fields = ["work_order", "delivery_challan", "invoice_no", "qty","remark",]
        widgets = {
        "remark": forms.Textarea(attrs={'rows': 1, 'cols': 80,
                                             'style': 'overflow: hidden',
                                             'oninput': "this.style.height='auto'; this.style.height=`${this.scrollHeight}px`",
                                             'onfocus': "this.style.height='auto'; this.style.height=`${this.scrollHeight}px`",
                                             'list': 'itemlist'
                                             })
    }


class TestParameterForm(forms.ModelForm):
    class Meta:
        model = TestParameter
        fields = ["standard_parameter", "result"]   # 'coa' removed — inline formset sets it

    def __init__(self, *args, **kwargs):
        coa = kwargs.pop('coa', None)
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_show_labels = False

        # When editing an existing row, fall back to its own coa
        if coa is None and self.instance and self.instance.pk:
            coa = self.instance.coa

        if coa and coa.jobname.itemmaster_id:
            allowed_ids = JobCoa.objects.filter(
                job=coa.jobname
            ).values_list('standard_parameter_id', flat=True)

            self.fields['standard_parameter'].queryset = (
                StdParameter.objects.filter(id__in=allowed_ids)
            )
        else:
            self.fields['standard_parameter'].queryset = StdParameter.objects.none()


class CoaAdminForm(forms.ModelForm):
    """Administrative fields only — allowed even after approval."""
    class Meta:
        model = Coa
        fields = ["work_order", "delivery_challan", "invoice_no", "qty"]