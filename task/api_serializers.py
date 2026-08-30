from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Task, Notification


class UserLookupSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'name']

    def get_name(self, obj):
        return obj.get_full_name() or obj.username


class TaskSerializer(serializers.ModelSerializer):
    """Mirrors TaskForm -- is_closed/close_date/request_to_close/
    request_date are all set only through the close/request_close actions
    below (toclosetask/requesttoclosetask in the old app), never directly
    through a plain PATCH."""
    task_alloted_to_name = serializers.CharField(source='task_alloted_to.get_full_name', read_only=True, default=None)
    createdby_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)

    class Meta:
        model = Task
        fields = [
            'id', 'taskname', 'description', 'target_date', 'priority',
            'task_alloted_to', 'task_alloted_to_name',
            'is_closed', 'close_date', 'request_to_close', 'request_date',
            'created', 'createdby', 'createdby_name', 'edited', 'editedby',
        ]
        read_only_fields = [
            'is_closed', 'close_date', 'request_to_close', 'request_date',
            'created', 'createdby', 'edited', 'editedby',
        ]


class NotificationSerializer(serializers.ModelSerializer):
    task_name = serializers.CharField(source='task.taskname', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'task', 'task_name', 'message', 'is_read', 'created']
        read_only_fields = fields
