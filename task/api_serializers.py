from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Task, TaskMsg, Notification, RecurringTask


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


class TaskMsgSerializer(serializers.ModelSerializer):
    """Mirrors TaskMsgForm + post_task_message -- `task` is written by the
    viewset (from ?task=/the posted task id, both access-checked there),
    never trusted straight off validated_data."""
    createdby_name = serializers.CharField(source='createdby.get_full_name', read_only=True, default=None)

    class Meta:
        model = TaskMsg
        fields = [
            'id', 'task', 'msg_text', 'msg_image', 'thumbnail', 'msg_file',
            'created', 'createdby', 'createdby_name',
        ]
        read_only_fields = ['task', 'thumbnail', 'created', 'createdby']

    def validate(self, attrs):
        if not attrs.get('msg_text') and not attrs.get('msg_image') and not attrs.get('msg_file'):
            raise serializers.ValidationError('Enter a message, image, or file.')
        return attrs


class RecurringTaskSerializer(serializers.ModelSerializer):
    task_alloted_to_name = serializers.CharField(
        source='task_alloted_to.get_full_name', read_only=True, default=None
    )

    class Meta:
        model = RecurringTask
        fields = [
            'id', 'taskname', 'description', 'priority',
            'task_alloted_to', 'task_alloted_to_name',
            'recur_type', 'day_of_month', 'months', 'interval_days',
            'last_created_date', 'advance_days', 'is_active', 'created', 'createdby',
        ]
        read_only_fields = ['last_created_date', 'created', 'createdby']
