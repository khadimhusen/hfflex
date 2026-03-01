from django import forms
from .models import *

from crispy_forms.helper import FormHelper


class ItemMasterForm(forms.ModelForm):
    itemname = forms.CharField(
        widget=forms.TextInput(attrs={'onBlur': "javascript:{this.value = this.value.toUpperCase();}"}))

    class Meta:
        model = ItemMaster
        fields = "__all__"
        exclude = ['createdby', 'editedby']


class ItemImageForm(forms.ModelForm):
    class Meta:
        model = ItemImage
        fields = ['imagename']


class RawMaterialForm(forms.ModelForm):
    class Meta:
        model = RawMaterial
        fields = ['materialname', 'item_mat_type', 'item_grade', 'size', 'micron']

    def __init__(self, *args, **kwargs):
        super(RawMaterialForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False


class ItemProcessForm(forms.ModelForm):
    class Meta:
        model = ItemProcess
        fields = ['process', 'unit','machine']

    def __init__(self, *args, **kwargs):
        super(ItemProcessForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False


class ItemColorForm(forms.ModelForm):
    class Meta:
        model = ItemColor
        fields = ['color', 'remark']

    def __init__(self, *args, **kwargs):
        super(ItemColorForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False

