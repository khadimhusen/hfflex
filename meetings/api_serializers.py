from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers

from . import richtext, services
from .models import ActionItem, Meeting, MeetingAttendee
from .permissions import can_delete_meeting, can_edit_meeting


def full_name(user):
    if user is None:
        return None
    return user.get_full_name().strip() or user.username


class AttendeeSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True), allow_null=True, required=False)
    name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    is_external = serializers.BooleanField(read_only=True)

    class Meta:
        model = MeetingAttendee
        fields = ['id', 'user', 'name', 'organisation', 'is_external']

    def validate(self, attrs):
        user = attrs.get('user')
        name = (attrs.get('name') or '').strip()
        if user is None and not name:
            raise serializers.ValidationError('Pick a user or type a name.')
        if user is not None:
            attrs['name'] = name or full_name(user)
            attrs['organisation'] = ''                 # an organisation is for outside people
        else:
            attrs['name'] = name
        return attrs


class ActionItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    owner = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True))
    owner_name = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)
    task = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = ActionItem
        fields = ['id', 'description', 'owner', 'owner_name', 'due_date', 'priority', 'status', 'task',
                  'done_at']
        read_only_fields = ['done_at']

    def get_owner_name(self, obj):
        return full_name(obj.owner)

    def validate_description(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Describe what needs to be done.')
        return value


class PreviousOpenItemSerializer(serializers.ModelSerializer):
    meeting_id = serializers.IntegerField(read_only=True)
    meeting_number = serializers.CharField(source='meeting.number', read_only=True)
    meeting_title = serializers.CharField(source='meeting.title', read_only=True)
    owner_name = serializers.SerializerMethodField()

    class Meta:
        model = ActionItem
        fields = ['id', 'meeting_id', 'meeting_number', 'meeting_title', 'description', 'owner_name', 'due_date']

    def get_owner_name(self, obj):
        return full_name(obj.owner)


class MeetingListSerializer(serializers.ModelSerializer):
    """One row of the meetings list. attendee_count / external_count / total_items /
    open_items are annotated by the viewset's queryset."""
    created_by_name = serializers.SerializerMethodField()
    attendee_count = serializers.IntegerField(read_only=True)
    external_count = serializers.IntegerField(read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    open_items = serializers.IntegerField(read_only=True)

    class Meta:
        model = Meeting
        fields = ['id', 'number', 'title', 'meeting_type', 'meeting_date', 'meeting_time', 'location', 'status',
                  'created_by_name', 'attendee_count', 'external_count', 'total_items', 'open_items']

    def get_created_by_name(self, obj):
        return full_name(obj.created_by)


class MeetingSerializer(serializers.ModelSerializer):
    attendees = AttendeeSerializer(many=True, required=False)
    action_items = ActionItemSerializer(many=True, required=False)
    created_by_name = serializers.SerializerMethodField()
    finalised_by_name = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    total_items = serializers.SerializerMethodField()
    open_items = serializers.SerializerMethodField()
    previous_open_items = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = [
            'id', 'number', 'title', 'meeting_type', 'meeting_date', 'meeting_time', 'location', 'agenda', 'minutes',
            'next_meeting_at', 'status', 'created_by', 'created_by_name', 'created_at', 'updated_at',
            'finalised_at', 'finalised_by_name', 'attendees', 'action_items', 'total_items', 'open_items',
            'previous_open_items', 'can_edit', 'can_delete',
        ]
        read_only_fields = ['number', 'status', 'created_by', 'created_at', 'updated_at', 'finalised_at']

    # ---- read-only extras -------------------------------------------------
    def get_created_by_name(self, obj):
        return full_name(obj.created_by)

    def get_finalised_by_name(self, obj):
        return full_name(obj.finalised_by)

    def _user(self):
        return self.context['request'].user

    def get_can_edit(self, obj):
        return can_edit_meeting(self._user(), obj)

    def get_can_delete(self, obj):
        return can_delete_meeting(self._user(), obj)

    def get_total_items(self, obj):
        return len(obj.action_items.all())

    def get_open_items(self, obj):
        return sum(1 for item in obj.action_items.all() if item.status == 'open')

    def get_previous_open_items(self, obj):
        if not obj.pk:
            return []
        return PreviousOpenItemSerializer(services.previous_open_items(obj), many=True).data

    # ---- validation ---------------------------------------------------------
    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Give the meeting a title.')
        return value

    # The agenda and minutes come from the rich-text editor: keep only safe formatting,
    # and store nothing when only empty lines were typed.
    def validate_agenda(self, value):
        return richtext.rich_html(value)

    def validate_minutes(self, value):
        return richtext.rich_html(value)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['agenda'] = richtext.rich_html(instance.agenda)
        data['minutes'] = richtext.rich_html(instance.minutes)
        return data

    def validate_attendees(self, rows):
        seen = set()
        for row in rows:
            user = row.get('user')
            if user is not None:
                if user.pk in seen:
                    raise serializers.ValidationError(f'{full_name(user)} is listed twice.')
                seen.add(user.pk)
        return rows

    # ---- writing ------------------------------------------------------------
    def _replace_attendees(self, meeting, rows):
        meeting.attendees.all().delete()
        MeetingAttendee.objects.bulk_create([MeetingAttendee(meeting=meeting, **row) for row in rows])

    def _sync_items(self, meeting, rows):
        """Rows with an id update that item; rows without one are new; items left
        out are removed -- unless they already have a task or are done, which is
        history (mark those done instead)."""
        actor = self._user()
        existing = {item.id: item for item in meeting.action_items.select_related('task', 'owner')}
        kept = set()
        for position, row in enumerate(rows):
            row = dict(row)
            item_id = row.pop('id', None)
            if item_id is None:
                item = ActionItem.objects.create(meeting=meeting, position=position, **row)
                if meeting.is_final:
                    services.create_task_for(item, actor)
            else:
                item = existing.get(item_id)
                if item is None:
                    raise serializers.ValidationError({'action_items': f'Action item {item_id} is not part of this meeting.'})
                for field, value in row.items():
                    setattr(item, field, value)
                item.position = position
                item.save()
                if meeting.is_final:
                    if item.task_id:
                        services.sync_task(item, actor)
                    else:
                        services.create_task_for(item, actor)
            kept.add(item.pk)
        for item_id, item in existing.items():
            if item_id in kept:
                continue
            if item.task_id or item.is_done:
                raise serializers.ValidationError({
                    'action_items': f'"{item.description}" already has a task. Mark it done instead of removing it.'})
            item.delete()

    @transaction.atomic
    def create(self, validated_data):
        attendees = validated_data.pop('attendees', [])
        items = validated_data.pop('action_items', [])
        meeting = Meeting.objects.create(created_by=self._user(), **validated_data)
        self._replace_attendees(meeting, attendees)
        self._sync_items(meeting, items)
        return meeting

    @transaction.atomic
    def update(self, instance, validated_data):
        attendees = validated_data.pop('attendees', None)
        items = validated_data.pop('action_items', None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if attendees is not None:
            self._replace_attendees(instance, attendees)
        if items is not None:
            self._sync_items(instance, items)
        return instance


class ActionItemListSerializer(serializers.ModelSerializer):
    """The "my action items" view: an item plus where it came from."""
    owner_name = serializers.SerializerMethodField()
    status = serializers.CharField(read_only=True)
    meeting_id = serializers.IntegerField(read_only=True)
    meeting_number = serializers.CharField(source='meeting.number', read_only=True)
    meeting_title = serializers.CharField(source='meeting.title', read_only=True)
    meeting_date = serializers.DateField(source='meeting.meeting_date', read_only=True)
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = ActionItem
        fields = ['id', 'description', 'owner', 'owner_name', 'due_date', 'priority', 'status', 'task',
                  'done_at', 'meeting_id', 'meeting_number', 'meeting_title', 'meeting_date', 'is_overdue']

    def get_owner_name(self, obj):
        return full_name(obj.owner)

    def get_is_overdue(self, obj):
        from django.utils import timezone
        return obj.status == 'open' and obj.due_date < timezone.now().date()
