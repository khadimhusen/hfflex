from datetime import datetime

from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from employee.models import Department
from .filters import QuotationFilter
from .models import Quotation, QuotationItem, Term
from .serializers import QuotationSerializer, TermSerializer


class TermViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Term.objects.all()
    serializer_class = TermSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None


class QuotationViewSet(viewsets.ModelViewSet):
    # Matches the old Django views' actual gate — @login_required only,
    # no department restriction on viewing/editing/approving by direct id.
    # The "only see your own" restriction (old quotationlist view) only ever
    # applied to the browse list, not to opening a quote by id — see get_queryset.
    serializer_class = QuotationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = QuotationFilter
    search_fields = ['partyname', 'contact']

    def get_queryset(self):
        qs = Quotation.objects.filter(is_deleted=False).prefetch_related(
            'quotationitems', 'additionalterms', 'quote_term'
        ).select_related('createdby', 'editedby', 'approvedby')

        if self.action == 'list':
            user = self.request.user
            can_see_all = Department.objects.filter(
                department_name='all_quote_list', user=user
            ).exists()
            if not can_see_all:
                qs = qs.filter(createdby=user)

        return qs

    @action(detail=False, methods=['get'])
    def filter_options(self, request):
        # Matches QuotationFilter's own createdby queryset restriction —
        # the old list only ever offered marketing-department users here.
        users = User.objects.filter(department__department_name='marketing').distinct()
        return Response({
            'createdby': [
                {'id': u.id, 'name': u.get_full_name() or u.username} for u in users
            ],
        })

    def perform_create(self, serializer):
        # createdby is set inside QuotationSerializer.create() from context['request']
        serializer.save()

    def perform_update(self, serializer):
        # Matches the old editquote view: once approved, only a
        # can_approve_quote user may still edit — enforced here too, not
        # just by hiding the Edit button (QuotationSerializer.can_edit).
        instance = serializer.instance
        if instance.approvedby and not Department.objects.filter(
            department_name='can_approve_quote', user=self.request.user
        ).exists():
            raise PermissionDenied('This quotation is approved — only an approver can edit it.')
        serializer.save()

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=['is_deleted'])

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        quote = self.get_object()

        if not Department.objects.filter(
            department_name='can_approve_quote', user=request.user
        ).exists():
            raise PermissionDenied('You are not allowed to approve quotations.')

        quote.approvedby = request.user
        quote.approved = datetime.now()
        quote.save(update_fields=['approvedby', 'approved'])

        return Response(self.get_serializer(quote).data)

    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """Matches the old copyquote view: copies the quote's own fields,
        line items, and quote_term selections. Additional terms are NOT
        copied — that's inherited from the original, not an oversight here.

        Builds a genuinely new Quotation/QuotationItem rather than resetting
        .pk on the fetched instance — this viewset's queryset prefetches
        related objects, and reusing the same Python object after resetting
        its pk serializes the stale prefetched cache instead of the new rows.
        """
        original = self.get_object()

        with transaction.atomic():
            original_items = list(original.quotationitems.all())
            original_term_ids = list(original.quote_term.values_list('id', flat=True))

            new_quote = Quotation.objects.create(
                partyname=original.partyname,
                add=original.add,
                contact=original.contact,
                quotedate=original.quotedate,
                remark=original.remark,
                design_rate=original.design_rate,
                no_of_design=original.no_of_design,
                cylinder_gst=original.cylinder_gst,
                material_gst=original.material_gst,
                createdby=request.user,
                editedby=request.user,
            )
            new_quote.quote_term.set(original_term_ids)

            for item in original_items:
                QuotationItem.objects.create(
                    quote=new_quote,
                    jobname=item.jobname,
                    dimension=item.dimension,
                    supply=item.supply,
                    structure=item.structure,
                    cyl_rate=item.cyl_rate,
                    no_of_cyl=item.no_of_cyl,
                    material_rate=item.material_rate,
                    pouch_per_kg=item.pouch_per_kg,
                    moq=item.moq,
                    unit=item.unit,
                    createdby=request.user,
                    editedby=request.user,
                )

        return Response(self.get_serializer(new_quote).data, status=201)
