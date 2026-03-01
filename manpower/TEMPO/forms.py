from django import forms
from .models import Shift, Activity, ShiftPerson
from employee.models import Worker


class NewShiftForm(forms.ModelForm):
    class Meta:
        model = Shift
        fields = ["shift",  "production_date"]


class ActivityForm(forms.ModelForm):
    class Meta:
        model = Activity
        fields = ["shift", "jobid", "qty", "speed", "makeready", "rolls", "lot", "downtime", "reason", "totaltime"]
        widgets = {
            'jobid': forms.NumberInput(),
            'shift': forms.HiddenInput()
        }
        labels = {
            "qty": "Meter/Nos." }

class ShiftPersonForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(ShiftPersonForm, self).__init__(*args, **kwargs)
        self.fields['person'].queryset = Worker.objects.filter(is_active=True).order_by('worker_name')


    class Meta:
        model = ShiftPerson
        fields = ["person","shift"]
        widgets = {
            "shift":forms.HiddenInput()
        }
