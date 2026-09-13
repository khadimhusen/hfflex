from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.urls import path

from .models import ViewName, Access, Worker, ViewAccess, Profile, Salary, Department
from .forms import CopyDepartmentForm


# ── Inline & simple admins ─────────────────────────────────────────────────────

class SalaryAdmin(admin.TabularInline):
    model = Salary


class WorkerAdmin(admin.ModelAdmin):
    list_display  = ('worker_name', 'emp_code', 'is_active', 'date_of_join', 'date_of_releave')
    search_fields = ['worker_name', 'emp_code', 'is_active']
    list_filter   = ['date_of_join', 'date_of_releave']
    inlines       = [SalaryAdmin]


admin.site.register(ViewName)
admin.site.register(Access)
admin.site.register(Profile)
admin.site.register(ViewAccess)
admin.site.register(Worker, WorkerAdmin)


# ── Department admin ───────────────────────────────────────────────────────────

class DepartmentAdminForm(forms.ModelForm):
    user = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model  = Department
        fields = '__all__'


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    form = DepartmentAdminForm
    list_display  = ('department_name',)
    # Searching by user answers "which departments is this person in?"
    search_fields = ['department_name', 'user__username', 'user__first_name', 'user__last_name']
    ordering      = ('department_name',)


# ── Copy-departments action (on UserAdmin and ProfileAdmin) ────────────────────

def _copy_departments_page(model_admin, request, back_to):
    """The intermediate page both actions lead to: pick a source user, then
    add (or replace with) their departments on the selected users. back_to
    is the changelist to return to afterwards."""
    target_ids   = request.session.get('copy_dept_target_ids', [])
    target_users = User.objects.filter(id__in=target_ids)

    if not target_users.exists():
        model_admin.message_user(request, "No users selected.", messages.WARNING)
        return redirect(back_to)

    if request.method == 'POST':
        form = CopyDepartmentForm(request.POST)
        if form.is_valid():
            source_user  = form.cleaned_data['source_user']
            replace      = form.cleaned_data['replace']
            source_depts = source_user.department.all()

            if not source_depts.exists():
                model_admin.message_user(
                    request,
                    f"'{source_user.username}' has no departments assigned.",
                    messages.WARNING,
                )
                return redirect(back_to)

            for user in target_users:
                if user == source_user:
                    continue
                if replace:
                    user.department.set(source_depts)
                else:
                    existing_ids = set(user.department.values_list('id', flat=True))
                    new_depts    = source_depts.exclude(id__in=existing_ids)
                    if new_depts.exists():
                        user.department.add(*new_depts)

            target_names = ", ".join(u.username for u in target_users)
            model_admin.message_user(
                request,
                f"Departments from '{source_user.username}' copied to: {target_names}",
                messages.SUCCESS,
            )
            del request.session['copy_dept_target_ids']
            return redirect(back_to)
    else:
        form = CopyDepartmentForm()

    return render(request, 'admin/copy_departments.html', {
        'form':         form,
        'target_users': target_users,
        'opts':         model_admin.model._meta,
        'title':        'Copy Departments',
    })


def copy_departments_action(modeladmin, request, queryset):
    request.session['copy_dept_target_ids'] = list(queryset.values_list('id', flat=True))
    return redirect('admin:copy_departments_intermediate')

copy_departments_action.short_description = "Copy departments from another user"


def copy_profile_departments_action(modeladmin, request, queryset):
    # Departments belong to the profile's user, so copy onto those users.
    request.session['copy_dept_target_ids'] = list(queryset.values_list('user_id', flat=True))
    return redirect('admin:copy_profile_departments_intermediate')

copy_profile_departments_action.short_description = "Copy departments from another user"


class CustomUserAdmin(BaseUserAdmin):
    actions = [copy_departments_action]
    list_display = BaseUserAdmin.list_display + ('is_active',)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'copy-departments/',
                self.admin_site.admin_view(self.copy_departments_view),
                name='copy_departments_intermediate',
            ),
        ]
        return custom_urls + urls

    def copy_departments_view(self, request):
        return _copy_departments_page(self, request, 'admin:auth_user_changelist')


class ProfileAdmin(admin.ModelAdmin):
    actions = [copy_profile_departments_action]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'copy-departments/',
                self.admin_site.admin_view(self.copy_departments_view),
                name='copy_profile_departments_intermediate',
            ),
        ]
        return custom_urls + urls

    def copy_departments_view(self, request):
        return _copy_departments_page(self, request, 'admin:employee_profile_changelist')


# Unregister the default UserAdmin / ProfileAdmin, re-register with ours
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
admin.site.unregister(Profile)
admin.site.register(Profile, ProfileAdmin)