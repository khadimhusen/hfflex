from django.utils import timezone
from django.db.models import OuterRef, Subquery, F, Q, ExpressionWrapper, DateTimeField, BooleanField
from django.db.models.functions import Coalesce
from .models import DealStageHistory


def annotate_deal_stall_fields(queryset):
    now = timezone.now()
    latest_stage_entry = DealStageHistory.objects.filter(
        deal=OuterRef('pk'), to_stage=OuterRef('stage')
    ).order_by('-changed_at').values('changed_at')[:1]

    qs = queryset.annotate(_stage_entry_from_history=Subquery(latest_stage_entry))
    qs = qs.annotate(stage_entered_at=Coalesce('_stage_entry_from_history', 'created_at'))
    qs = qs.annotate(
        stall_deadline=ExpressionWrapper(
            F('stage_entered_at') + F('stage__max_stall_time'), output_field=DateTimeField()
        )
    )
    qs = qs.annotate(
        is_stalled=ExpressionWrapper(
            Q(stage__max_stall_time__isnull=False) & Q(stall_deadline__lt=now),
            output_field=BooleanField(),
        )
    )
    return qs