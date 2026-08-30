import os

from django.contrib.auth.models import User
from django.db.models import Q
from django.http import FileResponse, Http404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Document, DocumentDownloadLog
from .api_serializers import (
    UserLookupSerializer, DocumentListSerializer, DocumentSerializer, DocumentDownloadLogSerializer,
)


def get_client_ip(request):
    """Verbatim port of the old view's get_client_ip."""
    real_ip = request.META.get('HTTP_X_REAL_IP')
    if real_ip:
        return real_ip
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class UserLookupViewSet(viewsets.ReadOnlyModelViewSet):
    """Viewer-selection list -- mirrors DocumentUploadForm/ManageViewersForm
    excluding the current user (they already have access as the owner)."""
    serializer_class = UserLookupSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return User.objects.filter(is_active=True).exclude(pk=self.request.user.pk).order_by(
            'first_name', 'username',
        )


class DocumentViewSet(viewsets.ModelViewSet):
    """Mirrors the whole documents app. No department gate on the
    permission class itself -- the old app never had one either (only
    @login_required); every document is individually scoped by
    Document.has_access() (creator, assigned viewer, or superuser),
    same as document_list/detail/download here.

    Every write here (plain .save()/.delete(), and .viewers.set() below)
    can trigger django_elasticsearch_dsl's auto-sync signal handler --
    see signal_processors.ResilientSignalProcessor for why a write
    failing to reach Elasticsearch doesn't roll back the real database
    change anymore. Nothing needs to be handled at this level."""
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return DocumentListSerializer
        return DocumentSerializer

    def get_queryset(self):
        user = self.request.user
        qs = Document.objects.select_related('uploaded_by').prefetch_related('viewers')
        if not user.is_superuser:
            qs = qs.filter(Q(uploaded_by=user) | Q(viewers=user)).distinct()

        if self.action == 'list':
            query = self.request.query_params.get('q', '').strip()
            if query:
                # The old app searched Elasticsearch (title/description/
                # uploader username, fuzzy) -- substituted with a plain
                # DB search rather than standing up ES for this port.
                qs = qs.filter(
                    Q(title__icontains=query) | Q(description__icontains=query)
                    | Q(uploaded_by__username__icontains=query),
                )
        return qs

    def get_object(self):
        # Deliberately NOT scoped by get_queryset()'s uploaded_by/viewers
        # filter here -- mirrors document_detail/download raising a real
        # 403 (PermissionDenied) for a document you can see the id of but
        # can't access, rather than a 404 that hides whether it exists.
        pk = self.kwargs['pk']
        doc = Document.objects.select_related('uploaded_by').prefetch_related(
            'viewers', 'download_logs__downloaded_by',
        ).filter(pk=pk).first()
        if not doc:
            raise Http404
        if self.action in ('retrieve', 'download', 'viewers') and not doc.has_access(self.request.user):
            raise PermissionDenied("You don't have access to this document.")
        return doc

    def perform_create(self, serializer):
        serializer.save(uploaded_by=self.request.user)

    def perform_update(self, serializer):
        doc = serializer.instance
        if doc.uploaded_by_id != self.request.user.id and not self.request.user.is_superuser:
            raise PermissionDenied("Only the uploader can edit this document.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.uploaded_by_id != self.request.user.id and not self.request.user.is_superuser:
            raise PermissionDenied("Only the uploader can delete this document.")
        if instance.file:
            instance.file.delete(save=False)
        instance.delete()

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Mirrors the old app's (second, actually-live) document_download:
        logs the download, then streams the file."""
        doc = self.get_object()
        if not doc.file or not os.path.exists(doc.file.path):
            raise Http404('File not found')

        DocumentDownloadLog.objects.create(
            document=doc, downloaded_by=request.user, ip_address=get_client_ip(request),
        )
        return FileResponse(
            doc.file.open('rb'), as_attachment=True, filename=os.path.basename(doc.file.name),
        )

    @action(detail=True, methods=['get', 'post'])
    def viewers(self, request, pk=None):
        """Mirrors manage_viewers(): GET lists current viewers (+ download
        history, mirroring detail.html), POST replaces the viewer set --
        both owner/superuser only."""
        doc = self.get_object()
        if doc.uploaded_by_id != request.user.id and not request.user.is_superuser:
            raise PermissionDenied('Only the uploader can manage viewers.')

        if request.method == 'POST':
            viewer_ids = request.data.get('viewers', [])
            doc.viewers.set(viewer_ids)

        logs = doc.download_logs.select_related('downloaded_by').all()[:20]
        return Response({
            'viewers': UserLookupSerializer(doc.viewers.all(), many=True).data,
            'download_logs': DocumentDownloadLogSerializer(logs, many=True).data,
        })
