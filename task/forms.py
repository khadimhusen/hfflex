from django import forms
from .models import Task, TaskMsg


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