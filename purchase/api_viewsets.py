from django.db.models import DecimalField, F, Sum
from django.http import FileResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from customer.models import Customer, Address
from material.models import Unit
from .models import Po, PoItem, PoImage, ExpectedDate, Term
from .api_serializers import (
    PoSerializer, PoItemSerializer, PoImageSerializer, ExpectedDateSerializer,
    SupplierLookupSerializer, ShipToLookupSerializer, DeliveryAddressLookupSerializer,
    UnitLookupSerializer, TermSerializer,
)
from .pdfviews import build_po_pdf_buffer
from .permissions import IsPurchaseUser
from .querysets import can_see_all_po, can_add_price, can_approve_po, can_edit_po
from .filters import PoFilter, PoItemFilter

# Matches forms.py's PoForm, which hardcodes delivery ('ship to') address
# options to HF Flex's own internal customer record.
HFFLEX_CUSTOMER_ID = 31


class SupplierLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Customer.objects.filter(active=True, is_supplier=True).order_by('name')
    serializer_class = SupplierLookupSerializer
    permission_classes = [IsPurchaseUser]
    search_fields = ['name']


class ShipToLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Customer.objects.filter(active=True).order_by('name')
    serializer_class = ShipToLookupSerializer
    permission_classes = [IsPurchaseUser]
    search_fields = ['name']


class DeliveryAddressLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Address.objects.filter(customer_id=HFFLEX_CUSTOMER_ID).order_by('addname')
    serializer_class = DeliveryAddressLookupSerializer
    permission_classes = [IsPurchaseUser]


class UnitLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Unit.objects.order_by('unit')
    serializer_class = UnitLookupSerializer
    permission_classes = [IsPurchaseUser]


class TermLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Term.objects.all().order_by('term')
    serializer_class = TermSerializer
    permission_classes = [IsPurchaseUser]


class PoViewSet(viewsets.ModelViewSet):
    """No delete view ever existed in the old app for this model either —
    POs only ever get created, edited, approved/unapproved, or cloned into
    a new one."""
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    queryset = Po.objects.select_related(
        'supplier', 'ship_to', 'delivery_at', 'createdby', 'approvedby', 'editedby',
    ).prefetch_related('poitem', 'poterm', 'itemexpecteddate', 'supplier__addresses', 'supplier__persons')
    serializer_class = PoSerializer
    permission_classes = [IsPurchaseUser]
    filterset_class = PoFilter
    # Listing columns like id/delivery_date/created are sortable in the SPA's
    # table — that needs real backend ordering support, since the default
    # DEFAULT_FILTER_BACKENDS (settings.py) doesn't include OrderingFilter.
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    ordering_fields = ['id', 'delivery_date', 'created']
    ordering = ['-id']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not can_see_all_po(user):
            qs = qs.filter(createdby=user)
        return qs

    def list(self, request, *args, **kwargs):
        # pototal is a Python @property (sum of qty*rate per line, rounded
        # per-line) -- recomputing it in the DB avoids an N+1 per PO (each
        # .pototal access would otherwise walk its own poitem.all()). The
        # DB sum skips the per-line rounding, which is fine for a total.
        response = super().list(request, *args, **kwargs)
        total = self.filter_queryset(self.get_queryset()).aggregate(
            total_amount=Sum(F('poitem__qty') * F('poitem__rate'), output_field=DecimalField()),
        )
        response.data['total_amount'] = total['total_amount'] or 0
        return response

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user, status='Pending')

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        if not can_approve_po(request.user):
            raise PermissionDenied('You are not authorized to approve purchase orders.')
        po = self.get_object()
        po.approvedby = request.user
        po.approve_date = timezone.now()
        po.save()
        return Response(self.get_serializer(po).data)

    @action(detail=True, methods=['post'], url_path='remove-approval')
    def remove_approval(self, request, pk=None):
        if not can_approve_po(request.user):
            raise PermissionDenied('You are not authorized to modify purchase order approval.')
        po = self.get_object()
        po.approvedby = None
        po.approve_date = None
        po.save()
        return Response(self.get_serializer(po).data)

    @action(detail=True, methods=['post'])
    def clone(self, request, pk=None):
        """Duplicates this PO's header fields and items into a brand-new
        Pending PO — mirrors the old deepclonepurchase flow, minus its
        two-step 'prefilled form you must still submit' UX: the SPA does it
        in one call and the user edits the new PO afterwards if needed."""
        source = self.get_object()
        new_po = Po.objects.create(
            supplier=source.supplier,
            delivery_date=source.delivery_date,
            payment_terms=source.payment_terms,
            tax1=source.tax1,
            tax2=source.tax2,
            transport=source.transport,
            remark=source.remark,
            ship_to=source.ship_to,
            delivery_at=source.delivery_at,
            status='Pending',
            createdby=request.user,
        )
        new_po.poterm.set(source.poterm.all())
        price_ok = can_add_price(request.user)
        for item in source.poitem.all():
            PoItem.objects.create(
                purchaseorder=new_po,
                description=item.description,
                category=item.category,
                qty=item.qty,
                unit=item.unit,
                rate=item.rate if price_ok else 0,
                rec_qty=0,
                createdby=request.user,
            )
        return Response(self.get_serializer(new_po).data, status=201)

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        """Same printable PDF as the old app's newpopdf view (reused as-is,
        see purchase.pdfviews.build_po_pdf_buffer) — not the SPA's editable
        detail page, a literal document meant to be sent to the supplier."""
        po = self.get_object()
        buffer = build_po_pdf_buffer(po)
        return FileResponse(
            buffer, content_type='application/pdf', filename=f'{po.id} - {po.supplier}.pdf',
        )


class PoItemViewSet(viewsets.ModelViewSet):
    queryset = PoItem.objects.select_related('purchaseorder', 'unit', 'createdby', 'editedby').order_by('id')
    serializer_class = PoItemSerializer
    permission_classes = [IsPurchaseUser]
    filterset_class = PoItemFilter

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not can_see_all_po(user):
            qs = qs.filter(purchaseorder__createdby=user)
        return qs

    def perform_create(self, serializer):
        po = serializer.validated_data['purchaseorder']
        if not can_edit_po(self.request.user, po):
            raise PermissionDenied('You are not authorized to add items to this purchase order.')
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        # 'purchaseorder' is writable (no UI ever offered reassigning an
        # item between POs, but nothing stops a raw API call from trying);
        # get_object()'s queryset scoping already vetted the CURRENT parent,
        # so only the NEW one needs checking here.
        new_po = serializer.validated_data.get('purchaseorder')
        if new_po and new_po != serializer.instance.purchaseorder and not can_edit_po(self.request.user, new_po):
            raise PermissionDenied('You are not authorized to move this item to that purchase order.')
        serializer.save(editedby=self.request.user)


class PoImageViewSet(viewsets.ModelViewSet):
    # Old app: addpoimage only ever creates — there was never a delete (or
    # edit) view for an uploaded PO image. PATCH is kept as a reasonable,
    # low-risk extension (e.g. fixing an imagename typo); DELETE is not.
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    queryset = PoImage.objects.select_related('po', 'createdby', 'editedby').order_by('-id')
    serializer_class = PoImageSerializer
    permission_classes = [IsPurchaseUser]
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ['po']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not can_see_all_po(user):
            qs = qs.filter(po__createdby=user)
        return qs

    def perform_create(self, serializer):
        po = serializer.validated_data['po']
        if not can_edit_po(self.request.user, po):
            raise PermissionDenied('You are not authorized to add images to this purchase order.')
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        new_po = serializer.validated_data.get('po')
        if new_po and new_po != serializer.instance.po and not can_edit_po(self.request.user, new_po):
            raise PermissionDenied('You are not authorized to move this image to that purchase order.')
        serializer.save(editedby=self.request.user)


class ExpectedDateViewSet(viewsets.ModelViewSet):
    # Old app: these only ever get logged and listed, never edited/deleted.
    http_method_names = ['get', 'post', 'head', 'options']
    queryset = ExpectedDate.objects.select_related('po', 'createdby').order_by('-id')
    serializer_class = ExpectedDateSerializer
    permission_classes = [IsPurchaseUser]
    filterset_fields = ['po']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not can_see_all_po(user):
            qs = qs.filter(po__createdby=user)
        return qs

    def perform_create(self, serializer):
        po = serializer.validated_data['po']
        if not can_edit_po(self.request.user, po):
            raise PermissionDenied('You are not authorized to log a follow-up date for this purchase order.')
        instance = serializer.save(createdby=self.request.user)
        # Mirrors the old poexpeteddate view: logging a new follow-up date
        # also updates the PO's own delivery_date to match.
        Po.objects.filter(id=instance.po_id).update(delivery_date=instance.expected_date)
