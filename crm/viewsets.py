from rest_framework.exceptions import PermissionDenied
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import (
    Pipeline, DealStageName, DealStage, DealStageHistory,
    Account, Contact, Deal, Lead, Note, DealAttachment, DealTask
)
from django.db.models import Sum, DecimalField
from .serializers import (
    PipelineSerializer, DealStageNameSerializer, DealStageSerializer,
    AccountSerializer, ContactSerializer, DealSerializer,
    DealStageChangeSerializer, DealStageHistorySerializer, LeadSerializer, CrmUserSerializer,
    NoteSerializer, DealAttachmentSerializer, DealTaskSerializer
)
from .filters import DealFilter, LeadFilter, AccountFilter, ContactFilter
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction
from .querysets import crm_users
from django.utils import timezone
from django.db.models import OuterRef, Subquery, F, Q, ExpressionWrapper, DateTimeField, BooleanField
from django.db.models.functions import Coalesce


class PipelineViewSet(viewsets.ModelViewSet):
    queryset = Pipeline.objects.prefetch_related('stages__dealstagename')
    serializer_class = PipelineSerializer


class DealStageNameViewSet(viewsets.ModelViewSet):
    queryset = DealStageName.objects.all()
    serializer_class = DealStageNameSerializer


class DealStageViewSet(viewsets.ModelViewSet):
    queryset = DealStage.objects.select_related('pipeline', 'dealstagename')
    serializer_class = DealStageSerializer
    filterset_fields = ['pipeline']


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.select_related('owner')
    serializer_class = AccountSerializer
    filterset_class = AccountFilter
    search_fields = ['name', 'phone', 'account_number']


class ContactViewSet(viewsets.ModelViewSet):
    queryset = Contact.objects.select_related('account', 'owner')
    serializer_class = ContactSerializer
    filterset_class = ContactFilter
    search_fields = ['first_name', 'last_name', 'email', 'phone']


class DealViewSet(viewsets.ModelViewSet):
    queryset = Deal.objects.all()
    serializer_class = DealSerializer
    filterset_class = DealFilter
    search_fields = ['name', 'account__name']

    def get_queryset(self):
        now = timezone.now()

        latest_stage_entry = DealStageHistory.objects.filter(
            deal=OuterRef('pk'), to_stage=OuterRef('stage')
        ).order_by('-changed_at').values('changed_at')[:1]

        qs = Deal.objects.select_related('pipeline', 'stage__dealstagename', 'account', 'contact', 'owner')
        qs = qs.annotate(_stage_entry_from_history=Subquery(latest_stage_entry))
        qs = qs.annotate(stage_entered_at=Coalesce('_stage_entry_from_history', 'created_at'))
        qs = qs.annotate(
            stall_deadline=ExpressionWrapper(
                F('stage_entered_at') + F('stage__max_stall_time'),
                output_field=DateTimeField(),
                )
        )
        qs = qs.annotate(
            is_stalled=ExpressionWrapper(
                Q(stage__max_stall_time__isnull=False) & Q(stall_deadline__lt=now),
                output_field=BooleanField(),
                )
        )
        return qs

    # ...existing change_stage and summary actions stay exactly as they are

    @action(detail=True, methods=['patch'], url_path='change-stage')
    def change_stage(self, request, pk=None):
        """The ONLY correct way to move a deal's stage. Writes a
        DealStageHistory row server-side — the client never gets to
        do this silently through a plain PATCH on `stage`."""
        deal = self.get_object()
        serializer = DealStageChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_stage = serializer.validated_data['stage']
        lost_reason = serializer.validated_data['lost_reason'].strip()

        if new_stage.pipeline_id != deal.pipeline_id:
            return Response(
                {'stage': f'"{new_stage}" does not belong to this deal\'s pipeline.'},
                status=400,
            )

        if new_stage.is_lost and not lost_reason:
            return Response(
                {'lost_reason': 'A reason is required when marking a deal as lost.'},
                status=400,
            )

        old_stage = deal.stage
        deal.stage = new_stage

        update_fields = ['stage', 'updated_at']
        if new_stage.is_won or new_stage.is_lost:
            deal.closing_date = timezone.now().date()
            update_fields.append('closing_date')
        elif old_stage.is_won or old_stage.is_lost:
            deal.closing_date = None
            update_fields.append('closing_date')

        if new_stage.is_lost:
            deal.lost_reason = lost_reason
            update_fields.append('lost_reason')
        elif old_stage.is_lost:
            deal.lost_reason = ''
            update_fields.append('lost_reason')

        deal.save(update_fields=update_fields)

        DealStageHistory.objects.create(
            deal=deal,
            from_stage=old_stage,
            to_stage=new_stage,
            changed_by=request.user,
        )

        return Response(DealSerializer(deal, context={'request': request}).data)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        qs = self.filter_queryset(self.get_queryset())

        expected_revenue_expr = ExpressionWrapper(
            F('amount') * F('stage__probability') / 100.0,
            output_field=DecimalField(max_digits=14, decimal_places=2),
            )

        total_count = qs.count()  # true total, matches pagination exactly

        revenue_agg = qs.exclude(amount__isnull=True).aggregate(
            total_expected_revenue=Sum(expected_revenue_expr),
            total_amount=Sum('amount'),
        )

        return Response({
            'total_expected_revenue': revenue_agg['total_expected_revenue'] or 0,
            'total_amount': revenue_agg['total_amount'] or 0,
            'count': total_count,
        })


class DealStageHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DealStageHistory.objects.select_related(
        'deal', 'from_stage__dealstagename', 'to_stage__dealstagename', 'changed_by'
    )
    serializer_class = DealStageHistorySerializer
    filterset_fields = ['deal', 'changed_by']


class LeadViewSet(viewsets.ModelViewSet):
    queryset = Lead.objects.select_related(
        'owner', 'converted_account', 'converted_contact', 'converted_deal'
    )
    serializer_class = LeadSerializer
    filterset_class = LeadFilter
    search_fields = ['first_name', 'last_name', 'company', 'phone', 'email']

    def get_queryset(self):
        qs = Lead.objects.select_related(
            'owner', 'converted_account', 'converted_contact', 'converted_deal'
        )
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return qs
        return qs.filter(owner=user)

    @action(detail=True, methods=['post'])
    def convert(self, request, pk=None):
        lead = self.get_object()

        if lead.is_converted:
            return Response({'detail': 'This lead has already been converted.'}, status=400)

        owner = crm_users().filter(id=request.data.get('owner')).first()
        if owner is None:
            return Response({'owner': ['A valid owner is required.']}, status=400)

        with transaction.atomic():
            account_action = request.data.get('account_action', 'new')

            if account_action == 'existing':
                account = Account.objects.filter(id=request.data.get('account_id')).first()
                if account is None:
                    return Response({'account_id': ['Account not found.']}, status=400)
            else:
                account = Account.objects.create(
                    name=lead.company or lead.name,
                    phone=lead.phone,
                    billing_city=lead.city,
                    billing_state=lead.state,
                    billing_country=lead.country,
                    industry=lead.industry,
                    annual_revenue=lead.annual_revenue,
                    owner=owner,
                )

            contact = Contact.objects.create(
                first_name=lead.first_name,
                last_name=lead.last_name,
                account=account,
                title=lead.title,
                email=lead.email,
                phone=lead.phone,
                mobile=lead.mobile,
                lead_source=lead.lead_source,
                owner=owner,
            )

            deal = None
            if request.data.get('create_deal'):
                deal_data = request.data.get('deal') or {}
                stage = DealStage.objects.filter(id=deal_data.get('stage')).first()
                if stage is None:
                    return Response({'deal': {'stage': ['A valid stage is required.']}}, status=400)

                deal = Deal.objects.create(
                    name=deal_data.get('name') or (lead.company or lead.name),
                    pipeline=stage.pipeline,
                    stage=stage,
                    account=account,
                    contact=contact,
                    amount=deal_data.get('amount'),
                    closing_date=deal_data.get('closing_date') or None,
                    description=deal_data.get('description') or lead.description or '',
                    owner=owner,
                )

            lead.is_converted = True
            lead.converted_account = account
            lead.converted_contact = contact
            lead.converted_deal = deal
            lead.converted_at = timezone.now()
            lead.owner = owner
            lead.save()

        return Response({
            'account': account.id,
            'contact': contact.id,
            'deal': deal.id if deal else None,
        })


class CrmUserViewSet(viewsets.ReadOnlyModelViewSet):
    """Just for populating owner dropdowns in the frontend — never
    exposes anything beyond name/username for crm_user department staff."""
    queryset = crm_users()
    serializer_class = CrmUserSerializer



class NoteViewSet(viewsets.ModelViewSet):
    queryset = Note.objects.select_related('created_by')
    serializer_class = NoteSerializer
    filterset_fields = ['deal', 'lead', 'contact', 'account']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        note = self.get_object()
        if note.created_by_id != self.request.user.id and not self.request.user.is_staff:
            raise PermissionDenied('You can only edit your own notes.')
        serializer.save()

    def perform_destroy(self, instance):
        if instance.created_by_id != self.request.user.id and not self.request.user.is_staff:
            raise PermissionDenied('You can only delete your own notes.')
        instance.delete()


class DealAttachmentViewSet(viewsets.ModelViewSet):
    queryset = DealAttachment.objects.select_related('uploaded_by')
    serializer_class = DealAttachmentSerializer
    filterset_fields = ['deal']
    parser_classes = [MultiPartParser, FormParser]

    def perform_create(self, serializer):
        uploaded_file = self.request.FILES.get('file')
        serializer.save(
            uploaded_by=self.request.user,
            original_filename=uploaded_file.name if uploaded_file else '',
        )


class DealTaskViewSet(viewsets.ModelViewSet):
    queryset = DealTask.objects.select_related('owner', 'deal')
    serializer_class = DealTaskSerializer
    filterset_fields = ['deal', 'is_closed', 'owner']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=False, methods=['get'])
    def due_reminders(self, request):
        """Polled by the frontend — reminders that have hit their time,
        belong to the current user, and haven't been dismissed yet."""
        now = timezone.now()
        due = DealTask.objects.filter(
            owner=request.user,
            is_closed=False,
            reminder_enabled=True,
            reminder_dismissed=False,
            reminder_at__lte=now,
        ).select_related('deal')
        serializer = self.get_serializer(due, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def dismiss_reminder(self, request, pk=None):
        task = self.get_object()
        task.reminder_dismissed = True
        task.save(update_fields=['reminder_dismissed'])
        return Response({'status': 'dismissed'})