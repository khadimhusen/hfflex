from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser

from customer.models import Customer
from material.models import Unit
from .models import PreOrder, JobName
from .api_serializers import (
    PreOrderSerializer, JobNameSerializer, CustomerLookupSerializer, UnitLookupSerializer,
)
from .permissions import IsPreorderUser
from .querysets import can_edit_preorder
from .filters import PreOrderFilter


class CustomerLookupViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only customer-name lookup for the preorder 'customer' field's
    autocomplete — see CustomerLookupSerializer for why this doesn't just
    hit customerApi."""
    queryset = Customer.objects.filter(is_customer=True).order_by('name')
    serializer_class = CustomerLookupSerializer
    permission_classes = [IsPreorderUser]
    search_fields = ['name']


class UnitLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Unit.objects.order_by('unit')
    serializer_class = UnitLookupSerializer
    permission_classes = [IsPreorderUser]


class PreOrderViewSet(viewsets.ModelViewSet):
    """No delete view ever existed in the old app for this model either —
    preorders only ever get created, edited, or finalized/reopened."""
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    queryset = PreOrder.objects.select_related('createdby', 'editedby')
    serializer_class = PreOrderSerializer
    permission_classes = [IsPreorderUser]
    filterset_class = PreOrderFilter

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        if not can_edit_preorder(self.request.user, serializer.instance):
            raise PermissionDenied(
                "Only the preorder's creator (before final submission), or staff, can change it."
            )
        serializer.save(editedby=self.request.user)


class JobNameViewSet(viewsets.ModelViewSet):
    """Every write here re-checks can_edit_preorder on the PARENT preorder —
    in the old app this lived behind the single editpreorder view's
    permission check, covering the whole inline formset at once."""
    queryset = JobName.objects.select_related('preorder', 'unit', 'createdby', 'editedby', 'job').order_by('id')
    serializer_class = JobNameSerializer
    permission_classes = [IsPreorderUser]
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ['preorder']

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('pending') == 'true':
            qs = qs.filter(job__isnull=True)
        return qs

    def perform_create(self, serializer):
        preorder = serializer.validated_data['preorder']
        if not can_edit_preorder(self.request.user, preorder):
            raise PermissionDenied('You are not authorized to add jobs to this preorder.')
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        if not can_edit_preorder(self.request.user, serializer.instance.preorder):
            raise PermissionDenied('You are not authorized to edit jobs on this preorder.')
        serializer.save(editedby=self.request.user)

    def perform_destroy(self, instance):
        if not can_edit_preorder(self.request.user, instance.preorder):
            raise PermissionDenied('You are not authorized to delete jobs from this preorder.')
        instance.delete()
