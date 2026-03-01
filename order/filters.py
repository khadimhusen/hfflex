import django_filters

from itemmaster.models import Process
from material.models import Material
from .models import Order, Job, JobProcess, JobMaterial
from django import forms
from .choices import jobchoices, processchoices, cylinderchoices


def jobsstatus(request):
    if request is None:
        return Job.objects.none()
    return Job.objects.all()


class OrderFilter(django_filters.FilterSet):
    created__gt = django_filters.DateFilter(label="From", field_name='created', lookup_expr='gt',
                                            input_formats=('%d/%m/%Y',))
    created__lt = django_filters.DateFilter(label="To", field_name='created', lookup_expr='lt',
                                            input_formats=('%d/%m/%Y',))
    customer = django_filters.CharFilter(field_name='customer__name', label="Customer", lookup_expr='icontains')

    class Meta:
        model = Order
        fields = ['createdby', 'status']


class JobFilter(django_filters.FilterSet):
    created__gt = django_filters.DateFilter(label="From Date", field_name='created', lookup_expr='gt',
                                            input_formats=('%d/%m/%Y',))
    created__lt = django_filters.DateFilter(label="To Date", field_name='created', lookup_expr='lt',
                                            input_formats=('%d/%m/%Y',))
    film__gte = django_filters.NumberFilter(field_name='film_size', label='From size', lookup_expr='gte')
    film__lte = django_filters.NumberFilter(field_name='film_size', label='To size', lookup_expr='lte')
    itemname = django_filters.CharFilter(field_name='itemname', lookup_expr='icontains')
    joborder__customer = django_filters.CharFilter(field_name='joborder__customer__name', lookup_expr='icontains',
                                                   label='customer')

    class Meta:
        model = Job
        fields = ['id', 'joborder__customer', 'jobstatus', 'supply_form']


class JobProcessFilter1(django_filters.FilterSet):
    created__gt = django_filters.DateFilter(label="From", field_name='created', lookup_expr='gte',
                                            input_formats=('%d/%m/%Y',))
    created__lt = django_filters.DateFilter(label="To", field_name='created', lookup_expr='lte',
                                            input_formats=('%d/%m/%Y',))
    job = django_filters.CharFilter(field_name='job__itemname', label='jobname', lookup_expr='icontains')
    customer = django_filters.CharFilter(field_name='job__joborder__customer__name', label='customer',
                                         lookup_expr='icontains')
    job__jobstatus = django_filters.MultipleChoiceFilter(choices=jobchoices, widget=forms.CheckboxSelectMultiple())
    status = django_filters.MultipleChoiceFilter(choices=processchoices, widget=forms.CheckboxSelectMultiple())
    cylinder = django_filters.MultipleChoiceFilter(field_name='job__itemmaster__cylinder_status',
                                                   widget=forms.CheckboxSelectMultiple(), label="cylinder",
                                                   choices=cylinderchoices)

    class Meta:
        model = JobProcess
        fields = ['id', 'process', 'status', 'job__supply_form', 'job__jobstatus']


class JobProcessFilter(django_filters.FilterSet):
    created__gt = django_filters.DateFilter(label="From", field_name='created', lookup_expr='gte',
                                            input_formats=('%d/%m/%Y',))
    created__lt = django_filters.DateFilter(label="To", field_name='created', lookup_expr='lte',
                                            input_formats=('%d/%m/%Y',))
    job = django_filters.CharFilter(field_name='job__itemname', label='jobname', lookup_expr='icontains')
    customer = django_filters.CharFilter(field_name='job__joborder__customer__name', label='customer',
                                         lookup_expr='icontains')
    job__jobstatus = django_filters.MultipleChoiceFilter(choices=jobchoices, widget=forms.CheckboxSelectMultiple())
    status = django_filters.MultipleChoiceFilter(choices=processchoices, widget=forms.CheckboxSelectMultiple())
    cylinder = django_filters.MultipleChoiceFilter(field_name='job__itemmaster__cylinder_status',
                                                   widget=forms.CheckboxSelectMultiple(), label="cylinder",
                                                   choices=cylinderchoices)

    # Cascade filter for process flow
    cascade_filter = django_filters.ChoiceFilter(
        method='filter_cascade_process',
        label='Cascade Status Filter',
        initial="",
        choices=[
            ('', 'All'),
            ('printing_done_lamination_pending', 'Printing Done → Lamination Pending'),
            ('lamination_done_slitting_pending', 'Lamination Done → Slitting Pending'),
            ('slitting_done_pouching_pending', 'Slitting Done → Pouching Pending'),
        ]
    )

    class Meta:
        model = JobProcess
        fields = ['id', 'process', 'status', 'job__supply_form', 'job__jobstatus']

    def filter_cascade_process(self, queryset, name, value):

        print("status", name)
        print("value", value)
        """
        Filter jobs based on cascade process status
        """
        if not value:
            return queryset

        from django.db.models import Exists, OuterRef

        # Define process mapping (adjust these based on your Process model)
        process_map = {
            'printing_done_lamination_pending': {
                'completed_process': 'Printing',
                'pending_process': 'Lamination'
            },
            'lamination_done_slitting_pending': {
                'completed_process': 'Lamination',
                'pending_process': 'Slitting'
            },
            'slitting_done_pouching_pending': {
                'completed_process': 'Slitting',
                'pending_process': 'Pouching'
            }
        }

        if value in process_map:
            config = process_map[value]
            print("config", config)

            # Get the Process objects
            try:
                completed_process = Process.objects.get(process=config['completed_process'])
                pending_process = Process.objects.get(process=config['pending_process'])

                print("completed process", completed_process)
                print("peinding process", pending_process)
            except JobProcess.DoesNotExist:
                return queryset.none()

            # Check if previous process is completed
            previous_process_completed = JobProcess.objects.filter(
                job=OuterRef('job'),
                process=completed_process,
                status__in=['Completed','Incomplete']
            )

            # Filter for current process with pending/incomplete status
            # where previous process is completed
            queryset = queryset.filter(
                process=pending_process,
                status__in=['Pending', 'Incomplete']
            ).annotate(
                previous_completed=Exists(previous_process_completed)
            ).filter(previous_completed=True)

        return queryset


class JobMaterialFilter(django_filters.FilterSet):
    job__joborder__customer = django_filters.CharFilter(label="customer", field_name='job__joborder__customer__name',
                                                        lookup_expr=("icontains"))
    job = django_filters.CharFilter(field_name='job__itemname', label='jobname', lookup_expr='icontains')
    job__jobstatus = django_filters.MultipleChoiceFilter(choices=jobchoices, widget=forms.CheckboxSelectMultiple())
    materialname = django_filters.MultipleChoiceFilter(choices=list(Material.objects.values_list("id", "name")),
                                                       widget=forms.CheckboxSelectMultiple())
    to_order = django_filters.RangeFilter()
    size = django_filters.RangeFilter()
    micron = django_filters.RangeFilter()
    orderedqty = django_filters.RangeFilter()
    receivedqty = django_filters.RangeFilter()

    class Meta:
        model = JobMaterial
        fields = ['materialname', 'item_mat_type', 'job__jobstatus', 'to_order',
                  'size', 'micron', 'orderedqty', 'receivedqty']
