from django import forms

from itemmaster.models import Problem
from .models import Shift, Activity, ShiftPerson, DowntimeReport
from employee.models import Worker
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column


class NewShiftForm(forms.ModelForm):
    class Meta:
        model = Shift
        fields = ["shift", "production_date"]


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ["shift", "jobid", "qty", "speed", "makeready","rolls", "tag","lot"]
        widgets = {
            'jobid': forms.NumberInput(),
            'shift': forms.HiddenInput()
        }
        labels = {
            "qty": "Meter/Nos."}


class ShiftPersonForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(ShiftPersonForm, self).__init__(*args, **kwargs)
        self.fields['person'].queryset = Worker.objects.filter(is_active=True).order_by('worker_name')

    class Meta:
        model = ShiftPerson
        fields = ["person", "shift"]
        widgets = {
            "shift": forms.HiddenInput()
        }


class DowntimeReportForm(forms.ModelForm):
    class Meta:
        model = DowntimeReport
        fields = ["reason", "downtime"]

    def __init__(self, *args, **kwargs):
        super(DowntimeReportForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False
        self.fields['reason'].queryset = Problem.objects.filter(is_active=True)
