from django import forms
from .models import *


# from django.forms.models import inlineformset_factory
# Create the form class.


class MaterialForm(forms.ModelForm):
    name = forms.CharField(
        widget=forms.TextInput(attrs={'onBlur': "javascript:{this.value = this.value.toUpperCase();}"}))

    class Meta:
        model = Material
        fields = '__all__'


class GradeForm(forms.ModelForm):
    grade = forms.CharField(
        widget=forms.TextInput(attrs={'onBlur': 'javascript:{this.value = this.valye.toUpperCase();'}))

    class Meta:
        model = Grade
        fields = '__all__'


class MatTypeForm(forms.ModelForm):
    mat_type = forms.CharField(
        widget=forms.TextInput(attrs={'onBlur': 'javascript:{this.value = this.value.toUpperCase();}'}))

    class Meta:
        model = MatType
        fields = '__all__'
