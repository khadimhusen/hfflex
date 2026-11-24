from datetime import date

from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget

from meetings.richtext import rich_html
from .models import Task, TaskMsg, RecurringTask


def description_widget():
    return CKEditor5Widget(config_name='task_description')


def clean_description_html(value):
    """What the editor sends -> safe HTML (scripts, styles, event handlers removed), or an error if empty."""
    html = rich_html(value)
    if not html:
        raise forms.ValidationError('Please describe the task.')
    return html


class TaskForm(forms.ModelForm):
    target_date = forms.DateField(input_formats=('%d/%m/%Y',))

    class Meta:
        model = Task
        fields = "__all__"
        exclude = ["is_closed", "request_to_close","createdby", "editedby"]
        widgets = {'description': description_widget()}

    def clean_description(self):
        return clean_description_html(self.cleaned_data.get('description'))

    def clean_target_date(self):
        target = self.cleaned_data.get('target_date')
        if target and not self.instance.pk and target < date.today():
            raise forms.ValidationError('The target date cannot be before today.')
        return target


class TaskMsgForm(forms.ModelForm):

    class Meta:
        model = TaskMsg
        fields = ["msg_text", "msg_image","msg_file"]


class RecurringTaskForm(forms.ModelForm):

    class Meta:
        model = RecurringTask
        fields = [
            'taskname', 'description', 'priority', 'task_alloted_to',
            'recur_type',
            'day_of_month', 'months',
            'interval_days',
            'advance_days', 'is_active'
        ]
        widgets = {'description': description_widget()}

    def clean_description(self):
        return clean_description_html(self.cleaned_data.get('description'))