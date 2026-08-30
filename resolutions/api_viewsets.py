from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response

from .models import Resolution, ResolutionDocument
from .api_serializers import ResolutionListSerializer, ResolutionSerializer, ResolutionDocumentSerializer
from .permissions import ResolutionPermission
from .querysets import can_edit_resolution, can_delete_resolution


class ResolutionViewSet(viewsets.ModelViewSet):
    """Mirrors resolution_list/detail/create/edit/delete. list/retrieve
    are open to anyone (see ResolutionPermission) -- the queryset itself
    hides drafts from anyone who isn't an editor, same as the old views."""
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']
    permission_classes = [ResolutionPermission]

    def get_serializer_class(self):
        if self.action == 'list':
            return ResolutionListSerializer
        return ResolutionSerializer

    def get_queryset(self):
        qs = Resolution.objects.select_related('created_by').prefetch_related('documents')
        user = self.request.user
        if not can_edit_resolution(user):
            qs = qs.filter(status='published')

        if self.action == 'list':
            q = self.request.query_params.get('q', '').strip()
            if q:
                qs = qs.filter(
                    Q(title__icontains=q) | Q(resolution_number__icontains=q)
                    | Q(meeting_location__icontains=q),
                )
            year = self.request.query_params.get('year', '').strip()
            if year:
                qs = qs.filter(meeting_date__year=year)
            meeting_type = self.request.query_params.get('meeting_type', '').strip()
            if meeting_type:
                qs = qs.filter(meeting_type=meeting_type)
        return qs

    def get_object(self):
        # Deliberately re-fetch unscoped by get_queryset()'s published-only
        # filter, then apply the SAME check the old resolution_detail()
        # did -- a 404 (not 403) for a draft you can see the id of but
        # aren't an editor for, matching that view's own raise Http404.
        pk = self.kwargs['pk']
        resolution = Resolution.objects.select_related('created_by').prefetch_related('documents').filter(
            pk=pk,
        ).first()
        if not resolution:
            raise NotFound
        if resolution.status != 'published' and not can_edit_resolution(self.request.user):
            raise NotFound
        return resolution

    def perform_create(self, serializer):
        resolution = serializer.save(created_by=self.request.user)
        if resolution.status == 'published':
            resolution.published_at = timezone.now()
            resolution.save(update_fields=['published_at'])

    def perform_update(self, serializer):
        resolution = serializer.save()
        if resolution.status == 'published' and not resolution.published_at:
            resolution.published_at = timezone.now()
            resolution.save(update_fields=['published_at'])

    def perform_destroy(self, instance):
        if not can_delete_resolution(self.request.user):
            raise PermissionDenied('Only admins can delete resolutions.')
        instance.delete()

    @action(detail=False, methods=['get'])
    def permissions(self, request):
        """Lets the frontend show/hide edit affordances (New Resolution,
        Edit, Delete) without needing a per-object fetch first."""
        return Response({
            'can_edit': can_edit_resolution(request.user),
            'can_delete': can_delete_resolution(request.user),
        })

    @action(detail=True, methods=['get', 'post'])
    def documents(self, request, pk=None):
        """GET lists attached documents; POST uploads a new one (editor
        only) -- mirrors the old app's inline DocumentFormSet, minus the
        formset machinery since here the Resolution always already exists
        by the time a document is attached."""
        resolution = self.get_object()
        if request.method == 'POST':
            if not can_edit_resolution(request.user):
                raise PermissionDenied("You don't have permission to add documents.")
            serializer = ResolutionDocumentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(resolution=resolution, uploaded_by=request.user)
            return Response(serializer.data, status=201)

        docs = resolution.documents.select_related('uploaded_by').all()
        return Response(ResolutionDocumentSerializer(docs, many=True).data)


class ResolutionDocumentViewSet(viewsets.ModelViewSet):
    """DELETE only (matching the formset's can_delete=True) -- creation
    goes through ResolutionViewSet.documents() above so a resolution
    reference and upload permission are always checked together."""
    http_method_names = ['get', 'delete', 'head', 'options']
    serializer_class = ResolutionDocumentSerializer
    permission_classes = [ResolutionPermission]
    filterset_fields = ['resolution']

    def get_queryset(self):
        qs = ResolutionDocument.objects.select_related('resolution', 'uploaded_by')
        if not can_edit_resolution(self.request.user):
            qs = qs.filter(resolution__status='published')
        return qs

    def perform_destroy(self, instance):
        if not can_edit_resolution(self.request.user):
            raise PermissionDenied("You don't have permission to delete documents.")
        instance.file.delete(save=False)
        instance.delete()
