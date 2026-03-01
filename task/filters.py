import django_filters

from .models import Task

class TaskFilter(django_filters.FilterSet):

    created__gt = django_filters.DateTimeFilter(label="From Date", field_name='created', lookup_expr='gte',
                                                input_formats=("%d/%m/%Y %H:%M",))
    created__lt = django_filters.DateTimeFilter(label="To Date", field_name='created', lookup_expr='lte',
                                                input_formats=("%d/%m/%Y %H:%M",))

    target__gt = django_filters.DateTimeFilter(label="Target Date", field_name='target_date', lookup_expr='gte',
                                                input_formats=("%d/%m/%Y %H:%M",))
    target__lt = django_filters.DateTimeFilter(label="To Target Date", field_name='target_date', lookup_expr='lte',
                                                input_formats=("%d/%m/%Y %H:%M",))

    taskname = django_filters.CharFilter(label="Task",field_name="taskname",lookup_expr="icontains")
    description = django_filters.CharFilter(label="Description",field_name="description",lookup_expr="icontains")

    class Meta:
        model = Task
        fields = [ 'taskname', 'priority','task_alloted_to', 'createdby','description',
                   'is_closed','request_to_close','target_date']


