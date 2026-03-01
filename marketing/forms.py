from django import forms
from .models import Route, RouteCustomer, Lead, Bunch
from crispy_forms.helper import FormHelper
from employee.models import Department


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ["customername", "cityname", "locationlink", "contact_number", "websitelink", "industry",
                  "lead_active"]


class RouteForm(forms.ModelForm):
    route_date = forms.DateField(input_formats=('%d/%m/%Y',))

    class Meta:
        model = Route
        fields = ["route_date", "marketing_person", "route_link"]

    def __init__(self, *args, **kwargs):
        super(RouteForm, self).__init__(*args, **kwargs)
        self.fields['marketing_person'].queryset = Department.objects.get(department_name="Markteing_only").user


class RouteCustomerForm(forms.ModelForm):
    class Meta:
        model = RouteCustomer
        fields = ["id", "customername", "route", "visitstatus", "nextvisit"]

    def __init__(self, routeuser=None, *args, **kwargs):
        super(RouteCustomerForm, self).__init__(*args, **kwargs)
        print("routeuser",routeuser)
        self.helper = FormHelper()
        self.helper.form_show_labels = False
        bunches = routeuser.bunch.all()
        self.fields['customername'].queryset = Lead.objects.filter(bunch__in=bunches, lead_active=True)

        if 'customername' in self.data:
            try:
                self.fields['customername'].queryset = Lead.objects.filter(bunch__in=bunches,
                                                                           lead_active=True).distinct()
                # | Lead.objects.filter(id=self.data.get("customername"))

            except (ValueError, TypeError):
                pass  # invalid input from the client; ignore and fallback to empty City queryset
        elif self.instance.pk:
            leadid = self.instance.customername.id

            self.fields['customername'].queryset = Lead.objects.filter(bunch__in=bunches,
                                                                       lead_active=True) | Lead.objects.filter(id=leadid)


class RouteFeedbackForm(forms.ModelForm):
    class Meta:
        model = RouteCustomer
        fields = ['presentation', 'need_analysis', 'packing_use', 'cost', 'terms_and_condition',
                  'old_supplier_relation', 'customer_sample', 'our_relation', 'reason',
                  'action_plan']
        widgets = {
            "action_plan": forms.Textarea(attrs={'rows': 3,
                                                 'style': 'overflow: hidden',
                                                 'oninput': "this.style.height='auto'; this.style.height=`${this.scrollHeight}px`",
                                                 'onfocus': "this.style.height='auto'; this.style.height=`${this.scrollHeight}px`",
                                                 'list': 'itemlist'
                                                 })
        }

    def __init__(self, *args, **kwargs):
        super(RouteFeedbackForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_show_labels = False


class BunchForm(forms.ModelForm):
    lead = forms.ModelMultipleChoiceField(
        queryset=Lead.objects.filter(lead_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Bunch
        fields = ["leaduser", "lead", "completed"]

    def __init__(self, *args, **kwargs):
        super(BunchForm, self).__init__(*args, **kwargs)
        self.fields['lead'].queryset = Lead.objects.filter(lead_active=True, bunch__isnull=True)
        self.fields['leaduser'].queryset = Department.objects.get(department_name="Marketing_only").user

        if 'lead' in self.data:
            print('self.data:', self.data.get('lead'))
            try:
                self.fields['lead'].queryset = Lead.objects.filter(lead_active=True, bunch__isnull=True) \
                                               | Lead.objects.filter(bunch=self.instance)
            except (ValueError, TypeError):
                pass  # invalid input from the client; ignore and fallback to empty City queryset
        elif self.instance.pk:
            self.fields['lead'].queryset = Lead.objects.filter(lead_active=True,
                                                               bunch__isnull=True) | self.instance.lead.all()
