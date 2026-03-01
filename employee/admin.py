from django.contrib import admin
from .models import ViewName, Access, Worker, ViewAccess, Profile, Salary, Department
from django import forms
from django.contrib.auth.models import User


class SalaryAdmin(admin.TabularInline):
    model = Salary


class WorkerAdmin(admin.ModelAdmin):
    list_display = ('worker_name', 'emp_code', 'is_active', 'date_of_join', 'date_of_releave')
    search_fields = ['worker_name', 'emp_code', 'is_active']
    list_filter = ['date_of_join', 'date_of_releave']
    inlines = [SalaryAdmin]

    class Meta:
        model = Worker


admin.site.register(ViewName)
admin.site.register(Access)
admin.site.register(Profile)
admin.site.register(ViewAccess)
admin.site.register(Worker, WorkerAdmin)


class DepartmentAdminForm(forms.ModelForm):
    user = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Department
        fields = '__all__'


class DepartmentAdmin(admin.ModelAdmin):
    form = DepartmentAdminForm


admin.site.register(Department, DepartmentAdmin)
