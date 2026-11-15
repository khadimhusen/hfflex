from django.db.models import Count, F, Func, Q, TextField, Value
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from . import services
from .api_serializers import ActionItemListSerializer, MeetingListSerializer, MeetingSerializer
from .exports import excel_filename, generate_meetings_xlsx
from .filters import OPEN_ITEM, MeetingFilter
from .models import ActionItem, Meeting
from .pdfs import build_minutes_pdf, pdf_filename
from .permissions import (
    IsMeetingUser, can_delete_meeting, can_edit_meeting, can_update_action_status, visible_meetings,
)

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def _without_tags(field):
    """The agenda/minutes with their HTML tags removed, so a search for "li" or
    "div" does not match every meeting."""
    return Func(F(field), Value('<[^>]*>'), Value(' '), Value('g'), function='regexp_replace',
                output_field=TextField())


class MeetingViewSet(viewsets.ModelViewSet):
    """Minutes of meeting. A user sees the meetings they created or attended
    (staff see all); only the creator or staff edit them. Other people's
    meetings simply 404, like the rest of the API."""
    permission_classes = [IsMeetingUser]
    filterset_class = MeetingFilter
    search_fields = ['number', 'title', 'agenda_text', 'minutes_text', 'location', 'attendees__name']

    def get_queryset(self):
        qs = Meeting.objects.select_related('created_by', 'finalised_by')
        qs = visible_meetings(self.request.user, qs)
        qs = qs.annotate(agenda_text=_without_tags('agenda'), minutes_text=_without_tags('minutes'))
        if self.action in ('list', 'excel'):
            open_filter = OPEN_ITEM
            return qs.annotate(
                attendee_count=Count('attendees', distinct=True),
                external_count=Count('attendees', filter=Q(attendees__user__isnull=True), distinct=True),
                total_items=Count('action_items', distinct=True),
                open_items=Count('action_items', filter=open_filter, distinct=True),
            )
        return qs.prefetch_related('attendees', 'action_items__owner', 'action_items__task')

    def get_serializer_class(self):
        return MeetingListSerializer if self.action == 'list' else MeetingSerializer

    def perform_update(self, serializer):
        if not can_edit_meeting(self.request.user, serializer.instance):
            raise PermissionDenied('Only the creator or a staff user can edit this meeting.')
        serializer.save()

    def perform_destroy(self, instance):
        if not can_delete_meeting(self.request.user, instance):
            raise PermissionDenied('Only a staff user can delete a finalised meeting.')
        instance.delete()

    @action(detail=True, methods=['post'])
    def finalise(self, request, pk=None):
        """Lock in the minutes: every action item becomes a task for its owner."""
        meeting = self.get_object()
        if not can_edit_meeting(request.user, meeting):
            raise PermissionDenied('Only the creator or a staff user can finalise this meeting.')
        services.finalise(meeting, request.user)
        meeting = self.get_queryset().get(pk=meeting.pk)
        return Response(MeetingSerializer(meeting, context=self.get_serializer_context()).data)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        meeting = self.get_object()
        response = HttpResponse(build_minutes_pdf(meeting), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{pdf_filename(meeting)}"'
        return response

    @action(detail=False, methods=['get'])
    def excel(self, request):
        """The meetings list (with the current filters) as an .xlsx."""
        meetings = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type=XLSX)
        response['Content-Disposition'] = f'attachment; filename="{excel_filename()}"'
        generate_meetings_xlsx(response, meetings)
        return response


class ActionItemViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Action items across the meetings the user can see. ?owner=me|<id>,
    ?status=open|done, ?overdue=true, ?meeting=<id>."""
    permission_classes = [IsMeetingUser]
    serializer_class = ActionItemListSerializer

    def get_queryset(self):
        user = self.request.user
        visible = visible_meetings(user, Meeting.objects.all()).values('pk')
        qs = ActionItem.objects.filter(meeting__in=visible).select_related('meeting', 'owner', 'task')
        params = self.request.query_params

        owner = params.get('owner')
        if owner == 'me':
            qs = qs.filter(owner=user)
        elif owner and owner.isdigit():
            qs = qs.filter(owner_id=int(owner))

        meeting = params.get('meeting')
        if meeting and meeting.isdigit():
            qs = qs.filter(meeting_id=int(meeting))

        done = Q(is_done=True) | Q(task__is_closed=True)
        status = params.get('status')
        if status == 'open':
            qs = qs.exclude(done)
        elif status == 'done':
            qs = qs.filter(done)

        if params.get('overdue') in ('true', '1'):
            qs = qs.exclude(done).filter(due_date__lt=timezone.now().date())
        return qs.order_by('due_date', 'id')

    def _item_for_status_change(self, request, pk):
        item = get_object_or_404(self.get_queryset(), pk=pk)
        if not can_update_action_status(request.user, item):
            raise PermissionDenied('Only the owner, the meeting creator or a staff user can do this.')
        return item

    @action(detail=True, methods=['post'], url_path='mark-done')
    def mark_done(self, request, pk=None):
        item = self._item_for_status_change(request, pk)
        services.mark_done(item, request.user)
        item.refresh_from_db()
        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=['post'])
    def reopen(self, request, pk=None):
        item = self._item_for_status_change(request, pk)
        services.reopen(item, request.user)
        item.refresh_from_db()
        return Response(self.get_serializer(item).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Counts for the menu badge: my open items, and how many are overdue."""
        mine = ActionItem.objects.filter(owner=request.user).exclude(Q(is_done=True) | Q(task__is_closed=True))
        return Response({
            'open': mine.count(),
            'overdue': mine.filter(due_date__lt=timezone.now().date()).count(),
        })
