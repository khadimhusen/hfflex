from django import forms
from .models import Task, TaskMsg, RecurringTask


class TaskForm(forms.ModelForm):
    target_date = forms.DateField(input_formats=('%d/%m/%Y',))

    class Meta:
        model = Task
        fields = "__all__"
        exclude = ["is_closed", "request_to_close","createdby", "editedby"]


class TaskMsgForm(forms.ModelForm):

    class Meta:
        model = TaskMsg
        fields = ["msg_text", "msg_image","msg_file"]


class RecurringTaskForm(forms.ModelForm):
    next_due_date = forms.DateField(
        input_formats=('%d/%m/%Y',),
        help_text="First/next due date"
    )

    class Meta:
        model = RecurringTask
        fields = ['taskname', 'description', 'priority', 'task_alloted_to',
                  'interval_days', 'advance_days', 'next_due_date', 'is_active']