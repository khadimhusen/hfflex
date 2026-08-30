from rest_framework import serializers

from .models import Resolution, ResolutionDocument
from .querysets import can_edit_resolution


class ResolutionDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source='uploaded_by.get_full_name', read_only=True, default=None)
    file_extension = serializers.SerializerMethodField()

    class Meta:
        model = ResolutionDocument
        fields = [
            'id', 'resolution', 'name', 'file', 'file_extension',
            'uploaded_at', 'uploaded_by', 'uploaded_by_name',
        ]
        read_only_fields = ['uploaded_at', 'uploaded_by']

    def get_file_extension(self, obj):
        return obj.file_extension()


class ResolutionListSerializer(serializers.ModelSerializer):
    """Lightweight row for list.html's table -- mirrors resolution_list()."""
    meeting_type_display = serializers.CharField(source='get_meeting_type_display', read_only=True)
    document_count = serializers.IntegerField(source='documents.count', read_only=True)

    class Meta:
        model = Resolution
        fields = [
            'id', 'resolution_number', 'title', 'meeting_date', 'meeting_location',
            'meeting_type', 'meeting_type_display', 'status', 'document_count',
        ]


class ResolutionSerializer(serializers.ModelSerializer):
    """Mirrors ResolutionForm's fields (resolution_number/title/content/
    meeting_date/meeting_location/meeting_type/status) plus
    header_height_mm/footer_height_mm -- new, not in the old app's form,
    for reserving blank letterhead space when printing."""
    meeting_type_display = serializers.CharField(source='get_meeting_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, default=None)
    can_edit = serializers.SerializerMethodField()
    documents = ResolutionDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Resolution
        fields = [
            'id', 'resolution_number', 'title', 'content',
            'meeting_date', 'meeting_location', 'meeting_type', 'meeting_type_display',
            'status', 'status_display', 'header_height_mm', 'footer_height_mm', 'can_edit', 'documents',
            'created_by', 'created_by_name', 'created_at', 'updated_at', 'published_at',
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'published_at']

    def get_can_edit(self, obj):
        request = self.context.get('request')
        return bool(request and can_edit_resolution(request.user))
