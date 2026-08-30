from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Document, DocumentDownloadLog


def display_name(user):
    return user.get_full_name() or user.username


class UserLookupSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'name']

    def get_name(self, obj):
        return display_name(obj)


class DocumentDownloadLogSerializer(serializers.ModelSerializer):
    downloaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentDownloadLog
        fields = ['id', 'downloaded_by_name', 'downloaded_at', 'ip_address']

    def get_downloaded_by_name(self, obj):
        return display_name(obj.downloaded_by)


class DocumentListSerializer(serializers.ModelSerializer):
    """Lightweight row for list.html's cards."""
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ['id', 'title', 'uploaded_by_name', 'created_at']

    def get_uploaded_by_name(self, obj):
        return display_name(obj.uploaded_by)


class DocumentSerializer(serializers.ModelSerializer):
    """Mirrors detail.html/upload.html. 'viewers' is writable on create
    (mirrors DocumentUploadForm) but read-only afterwards -- changing it
    later goes through the dedicated viewers action (mirrors
    manage_viewers being its own view/permission check)."""
    uploaded_by_name = serializers.SerializerMethodField()
    viewer_names = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id', 'title', 'description', 'file', 'file_name', 'uploaded_by', 'uploaded_by_name',
            'viewers', 'viewer_names', 'can_manage', 'created_at', 'updated_at',
        ]
        read_only_fields = ['uploaded_by', 'created_at', 'updated_at']
        extra_kwargs = {'file': {'write_only': False, 'required': True}}

    def get_uploaded_by_name(self, obj):
        return display_name(obj.uploaded_by)

    def get_viewer_names(self, obj):
        return [display_name(v) for v in obj.viewers.all()]

    def get_file_name(self, obj):
        import os
        return os.path.basename(obj.file.name) if obj.file else None

    def get_can_manage(self, obj):
        request = self.context.get('request')
        if not request:
            return False
        user = request.user
        return bool(user.is_superuser or obj.uploaded_by_id == user.id)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance is not None:
            # Mirrors manage_viewers being a separate view/permission --
            # 'viewers' is only writable on the initial upload.
            self.fields['viewers'].read_only = True
