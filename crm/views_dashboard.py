from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Deal, DealStageHistory
from django.utils import timezone

from django.db.models import (OuterRef, Subquery, F, Q, ExpressionWrapper, DateTimeField, BooleanField, Sum, Count,
                              DecimalField)
from django.db.models.functions import Coalesce, TruncMonth
from datetime import date

from .querysets import crm_users


def _add_months(d, offset):
    """Shift a date by `offset` whole months, landing on the 1st of the
    resulting month (avoids a dependency on python-dateutil)."""
    total = d.month - 1 + offset
    year = d.year + total // 12
    month = total % 12 + 1
    return date(year, month, 1)


class DealDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        owner_id = request.query_params.get('owner')
        now = timezone.now()

        latest_stage_entry = DealStageHistory.objects.filter(
            deal=OuterRef('pk'), to_stage=OuterRef('stage')
        ).order_by('-changed_at').values('changed_at')[:1]

        open_deals = Deal.objects.filter(stage__is_won=False, stage__is_lost=False)
        open_deals = open_deals.annotate(_stage_entry_from_history=Subquery(latest_stage_entry))
        open_deals = open_deals.annotate(stage_entered_at=Coalesce('_stage_entry_from_history', 'created_at'))
        open_deals = open_deals.annotate(
            stall_deadline=ExpressionWrapper(
                F('stage_entered_at') + F('stage__max_stall_time'), output_field=DateTimeField()
            )
        )
        open_deals = open_deals.annotate(
            is_stalled=ExpressionWrapper(
                Q(stage__max_stall_time__isnull=False) & Q(stall_deadline__lt=now),
                output_field=BooleanField(),
            )
        )

        won_deals = Deal.objects.filter(stage__is_won=True)

        if owner_id:
            open_deals = open_deals.filter(owner_id=owner_id)
            won_deals = won_deals.filter(owner_id=owner_id)

        expected_revenue_expr = ExpressionWrapper(
            F('amount') * F('stage__probability') / 100.0,
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )

        stage_counts = (
            open_deals
            .values('pipeline_id', 'pipeline__name', 'stage_id', 'stage__dealstagename__name', 'stage__order',
                    'stage__probability')
            .annotate(
                count=Count('id'),
                stalled_count=Count('id', filter=Q(is_stalled=True)),
                expected_revenue=Sum(expected_revenue_expr, filter=~Q(amount=None)),
            )
            .order_by('pipeline__name', 'stage__order')
        )

        open_expected_revenue = open_deals.exclude(amount__isnull=True).aggregate(
            total=Sum(expected_revenue_expr)
        )['total'] or 0

        date_from = request.query_params.get('closing_date_after')
        date_to = request.query_params.get('closing_date_before')
        if date_from:
            won_deals = won_deals.filter(closing_date__gte=date_from)
        if date_to:
            won_deals = won_deals.filter(closing_date__lte=date_to)

        won_agg = won_deals.aggregate(total=Sum('amount'), count=Count('id'))

        # Team-wide breakdown — always all owners, regardless of the `owner`
        # filter above (that filter narrows the stage cards, not this chart).
        all_open_deals = Deal.objects.filter(
            stage__is_won=False, stage__is_lost=False
        ).exclude(amount__isnull=True)
        open_amount_by_owner = (
            all_open_deals
            .values('owner_id', 'owner__first_name', 'owner__last_name', 'owner__username')
            .annotate(total=Sum(expected_revenue_expr))
            .order_by('-total')
        )

        # Last 12 months of Closed Won amount, for the `owner` filter above —
        # defaults to the logged-in user when no owner is selected.
        today = timezone.now().date()
        current_month_start = today.replace(day=1)
        months = [
            _add_months(current_month_start, -offset) for offset in range(11, -1, -1)
        ]
        my_won_rows = (
            Deal.objects.filter(
                owner_id=owner_id or request.user.id,
                stage__is_won=True,
                closing_date__gte=months[0],
            )
            .annotate(month=TruncMonth('closing_date'))
            .values('month')
            .annotate(total=Sum('amount'))
        )
        my_won_by_month = {row['month']: row['total'] or 0 for row in my_won_rows}
        my_monthly_closed_won = [
            {'month': m.strftime('%b %Y'), 'total': my_won_by_month.get(m, 0)}
            for m in months
        ]

        return Response({
            'stage_counts': [
                {
                    'pipeline_id': row['pipeline_id'],
                    'pipeline_name': row['pipeline__name'],
                    'stage_id': row['stage_id'],
                    'stage_name': row['stage__dealstagename__name'],
                    'probability': row['stage__probability'],
                    'count': row['count'],
                    'stalled_count': row['stalled_count'],
                    'expected_revenue': row['expected_revenue'] or 0,
                }
                for row in stage_counts
            ],
            'open_expected_revenue': open_expected_revenue,
            'closed_won': {
                'total': won_agg['total'] or 0,
                'count': won_agg['count'] or 0,
            },
            'open_amount_by_owner': [
                {
                    'owner_id': row['owner_id'],
                    'owner_name': f"{row['owner__first_name']} {row['owner__last_name']}".strip()
                                  or row['owner__username'],
                    'total': row['total'] or 0,
                }
                for row in open_amount_by_owner
            ],
            'my_monthly_closed_won': my_monthly_closed_won,
        })


from django.contrib.auth.models import User
from .models import DealStage, Lead

NOT_STAGE_CARDS = [
    ('Quote', 'Not Quoted'),
    ('Personal Visit', 'Not Visited'),
    ('Calling', 'Not Called'),
    ('Need Analysis', 'Not Analysed'),
    ('Advance', 'Not Advanced'),
    ('Design', 'Not Designed'),
    ('Courier', 'Not Courriered'),
    ('Waiting', 'Not Waited'),
]


class PersonalDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        as_user_id = request.query_params.get('as_user')
        if as_user_id and (user.is_staff or user.is_superuser):
            impersonated = User.objects.filter(id=as_user_id).first()
            if impersonated:
                user = impersonated

        open_deals = Deal.objects.filter(
            owner=user,
            pipeline__name__iexact='DATA SEARCH',
            stage__is_won=False,
            stage__is_lost=False,
        ).select_related('pipeline', 'stage__dealstagename')

        open_deals_count = open_deals.count()
        leads_count = Lead.objects.filter(owner=user, is_converted=False).count()

        # only DATA SEARCH's own stage order matters now
        stage_order_lookup = {
            s.dealstagename.name: s.order
            for s in DealStage.objects.select_related('pipeline', 'dealstagename')
            .filter(pipeline__name__iexact='DATA SEARCH')
        }

        data_search_pipeline = DealStage.objects.filter(pipeline__name__iexact='DATA SEARCH').first()
        pipeline_id = data_search_pipeline.pipeline_id if data_search_pipeline else None

        not_stage_counts = []
        for stage_name, label in NOT_STAGE_CARDS:
            target_order = stage_order_lookup.get(stage_name)
            if target_order is None:
                count = 0
            else:
                count = sum(1 for deal in open_deals if deal.stage.order < target_order)
            not_stage_counts.append({
                'label': label,
                'count': count,
                'stage_name': stage_name,
                'pipeline_id': pipeline_id,
            })

        expected_revenue_expr = ExpressionWrapper(
            F('amount') * F('stage__probability') / 100.0,
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
        open_amount_by_user = (
            Deal.objects.filter(
                pipeline__name__iexact='DATA SEARCH',
                stage__is_won=False,
                stage__is_lost=False,
            )
            .exclude(amount__isnull=True)
            .values('owner_id', 'owner__first_name', 'owner__last_name', 'owner__username')
            .annotate(total=Sum(expected_revenue_expr))
            .order_by('-total')
        )

        return Response({
            'open_deals_count': open_deals_count,
            'leads_count': leads_count,
            'not_stage_counts': not_stage_counts,
            'open_amount_by_user': [
                {
                    'owner_name': f"{row['owner__first_name']} {row['owner__last_name']}".strip()
                                  or row['owner__username'],
                    'total': row['total'] or 0,
                }
                for row in open_amount_by_user
            ],
        })


from django.contrib.auth.models import User
from .stall_utils import annotate_deal_stall_fields
from .models import Lead, Pipeline
from customer.querysets import customer_department_users
from itemmaster.querysets import itemmaster_department_users
from preorder.querysets import preorder_department_users
from purchase.querysets import purchase_department_users
from order.querysets import order_department_users
from production.querysets import report_department_users, dispatch_department_users, stock_department_users


def me_payload(u):
    is_staff = u.is_staff or u.is_superuser
    is_crm = is_staff or crm_users().filter(id=u.id).exists()
    is_customer = is_staff or customer_department_users().filter(id=u.id).exists()
    # TEMPORARY: itemmaster/preorder/purchase/order/production-report/
    # dispatch/stock restricted to staff/superuser only during rollout —
    # regular users see only crm/dashboard/costing/quotation for now.
    # Restore department-based access on each line below by swapping in
    # its commented-out version once ready for wider access. Matches the
    # same restriction on each module's own DRF permission class.
    is_itemmaster = is_staff
    # is_itemmaster = is_staff or itemmaster_department_users().filter(id=u.id).exists()
    is_preorder = is_staff
    # is_preorder = is_staff or preorder_department_users().filter(id=u.id).exists()
    is_purchase = is_staff
    # is_purchase = is_staff or purchase_department_users().filter(id=u.id).exists()
    is_order = is_staff
    # is_order = is_staff or order_department_users().filter(id=u.id).exists()
    is_production_report = is_staff
    # is_production_report = is_staff or report_department_users().filter(id=u.id).exists()
    is_dispatch = is_staff
    # is_dispatch = is_staff or dispatch_department_users().filter(id=u.id).exists()
    is_stock = is_staff
    # is_stock = is_staff or stock_department_users().filter(id=u.id).exists()
    return {
        'id': u.id,
        'name': f'{u.first_name} {u.last_name}'.strip() or u.username,
        'is_staff': is_staff,
        'is_crm_user': is_crm,  # kept for existing CRM-only checks
        'modules': {
            'crm': is_crm,
            'customer': is_customer,
            'itemmaster': is_itemmaster,
            'preorder': is_preorder,
            'purchase': is_purchase,
            'order': is_order,
            'productionReport': is_production_report,
            'dispatch': is_dispatch,
            'stock': is_stock,
        },
    }


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(me_payload(request.user))


class LoginView(APIView):
    """Session-based login for the SPA, mirroring myproject.views.user_login
    but returning JSON instead of redirecting. No CSRF priming needed —
    DRF's SessionAuthentication only enforces CSRF once a session already
    has an authenticated user, so an anonymous login POST isn't checked;
    django_login() below rotates the token and the response carries a
    fresh csrftoken cookie for the authenticated requests that follow."""
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username', '')
        password = request.data.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is None:
            return Response({'detail': 'Invalid username or password.'}, status=400)

        django_login(request, user)
        return Response(me_payload(user))


class LogoutView(APIView):
    """CRM-specific logout, kept separate from myproject.views.user_logout
    since that shared view also serves other old-app pages."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        django_logout(request)
        return Response({'detail': 'Logged out.'})


class MyDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        target_user = request.user
        view_as_id = request.query_params.get('view_as')
        if view_as_id and (request.user.is_staff or request.user.is_superuser):
            target_user = User.objects.filter(id=view_as_id).first() or request.user

        expected_revenue_expr = ExpressionWrapper(
            F('amount') * F('stage__probability') / 100.0,
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )

        open_deals = Deal.objects.filter(owner=target_user, stage__is_won=False, stage__is_lost=False)
        open_deals = annotate_deal_stall_fields(open_deals)

        my_open_deals_count = open_deals.count()
        my_leads_count = Lead.objects.filter(owner=target_user, is_converted=False).count()

        data_search_pipeline = Pipeline.objects.filter(name__iexact='DATA SEARCH').first()
        stalled_by_stage = []
        if data_search_pipeline:
            stalled_by_stage = list(
                open_deals.filter(pipeline=data_search_pipeline, is_stalled=True)
                .values('stage_id', 'stage__dealstagename__name', 'stage__order')
                .annotate(count=Count('id'))
                .order_by('stage__order')
            )

        funnel_stage_counts = (
            open_deals
            .values('pipeline_id', 'pipeline__name', 'stage_id', 'stage__dealstagename__name', 'stage__order',
                    'stage__probability')
            .annotate(
                count=Count('id'),
                expected_revenue=Sum(expected_revenue_expr, filter=~Q(amount=None)),
            )
            .order_by('pipeline__name', 'stage__order')
        )

        all_open_deals = Deal.objects.filter(stage__is_won=False, stage__is_lost=False).exclude(amount__isnull=True)
        open_amount_by_owner = (
            all_open_deals
            .values('owner_id', 'owner__first_name', 'owner__last_name', 'owner__username')
            .annotate(total=Sum(expected_revenue_expr))
            .order_by('-total')
        )

        return Response({
            'viewing_user': {
                'id': target_user.id,
                'name': f'{target_user.first_name} {target_user.last_name}'.strip() or target_user.username,
            },
            'my_open_deals': my_open_deals_count,
            'my_leads': my_leads_count,
            'stalled_by_stage': [
                {
                    'pipeline_id': data_search_pipeline.id if data_search_pipeline else None,
                    'stage_id': r['stage_id'],
                    'stage_name': r['stage__dealstagename__name'],
                    'count': r['count'],
                }
                for r in stalled_by_stage
            ],
            'funnel_stage_counts': [
                {
                    'pipeline_id': r['pipeline_id'], 'pipeline_name': r['pipeline__name'],
                    'stage_id': r['stage_id'], 'stage_name': r['stage__dealstagename__name'],
                    'probability': r['stage__probability'], 'count': r['count'],
                    'expected_revenue': r['expected_revenue'] or 0,
                }
                for r in funnel_stage_counts
            ],
            'open_amount_by_owner': [
                {
                    'owner_id': r['owner_id'],
                    'owner_name': f"{r['owner__first_name']} {r['owner__last_name']}".strip() or r['owner__username'],
                    'total': r['total'] or 0,
                }
                for r in open_amount_by_owner
            ],
        })
