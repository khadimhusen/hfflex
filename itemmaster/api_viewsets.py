from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Q

from customer.models import Customer
from material.models import Material, MatType, Grade, Unit, Commodity
from .models import (
    Machine, MachineTask, PouchType, LamiRubber, ItemMaster, ItemImage,
    RawMaterial, Process, ItemProcess, Color, ItemColor, Problem,
    AttributeMaster, ItemAttribute, CylinderMovement, StdParameter,
    ItemStandardParameter,
)
from .api_serializers import (
    MachineSerializer, MachineTaskSerializer, PouchTypeSerializer, LamiRubberSerializer,
    ItemMasterSerializer, ItemImageSerializer, RawMaterialSerializer, ProcessSerializer,
    ItemProcessSerializer, ColorSerializer, ItemColorSerializer, ProblemSerializer,
    AttributeMasterSerializer, ItemAttributeSerializer, CylinderMovementSerializer,
    StdParameterSerializer, ItemStandardParameterSerializer, CustomerLookupSerializer,
    MaterialLookupSerializer, MatTypeLookupSerializer, GradeLookupSerializer, UnitLookupSerializer,
    CommodityLookupSerializer,
)
from .permissions import IsItemmasterUser
from .querysets import can_edit_itemmaster
from .filters import ItemmasterFilter


class CustomerLookupViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only customer lookup for itemmaster's own dropdowns — see
    CustomerLookupSerializer for why this doesn't just hit customerApi."""
    serializer_class = CustomerLookupSerializer
    permission_classes = [IsItemmasterUser]
    search_fields = ['name']

    def get_queryset(self):
        qs = Customer.objects.order_by('name')

        if self.request.query_params.get('cylinder_suppliers') == 'true':
            return qs.filter(
                is_supplier=True, active=True, supplier_item__itemname='Cylinder',
            ).distinct()

        # Exact match on CylinderMovementForm's old queryset — GODOWN-1,
        # GODOWN-2, PRODUCTION, or the item's own customer. Deliberately
        # exact names, not a substring search, so a real customer like
        # "Production House Pvt Ltd" can never slip in as a false match.
        item_id = self.request.query_params.get('cylinder_locations_for_item')
        if item_id:
            itemmaster = ItemMaster.objects.filter(pk=item_id).select_related('itemcustomer').first()
            if not itemmaster:
                return qs.none()
            return qs.filter(
                Q(name='GODOWN-1') | Q(name='GODOWN-2') | Q(name='PRODUCTION')
                | Q(name=itemmaster.itemcustomer.name)
            )

        return qs


class MaterialLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Material.objects.order_by('name')
    serializer_class = MaterialLookupSerializer
    permission_classes = [IsItemmasterUser]
    search_fields = ['name']


class MatTypeLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MatType.objects.order_by('mat_type')
    serializer_class = MatTypeLookupSerializer
    permission_classes = [IsItemmasterUser]


class GradeLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Grade.objects.order_by('grade')
    serializer_class = GradeLookupSerializer
    permission_classes = [IsItemmasterUser]


class UnitLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Unit.objects.order_by('unit')
    serializer_class = UnitLookupSerializer
    permission_classes = [IsItemmasterUser]


class CommodityLookupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Commodity.objects.order_by('commodity')
    serializer_class = CommodityLookupSerializer
    permission_classes = [IsItemmasterUser]


class StampedCreateUpdateMixin:
    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)


class NoDeleteMixin:
    """Master/reference data other records point at — the old app never
    had a delete view for any of these either."""
    http_method_names = ['get', 'post', 'patch', 'head', 'options']


# ---- small lookup tables -------------------------------------------------

class PouchTypeViewSet(NoDeleteMixin, StampedCreateUpdateMixin, viewsets.ModelViewSet):
    queryset = PouchType.objects.select_related('createdby', 'editedby').order_by('pouchtype')
    serializer_class = PouchTypeSerializer
    permission_classes = [IsItemmasterUser]
    search_fields = ['pouchtype']


class LamiRubberViewSet(NoDeleteMixin, StampedCreateUpdateMixin, viewsets.ModelViewSet):
    queryset = LamiRubber.objects.select_related('createdby', 'editedby')
    serializer_class = LamiRubberSerializer
    permission_classes = [IsItemmasterUser]
    search_fields = ['rubber']


class ProcessViewSet(NoDeleteMixin, StampedCreateUpdateMixin, viewsets.ModelViewSet):
    queryset = Process.objects.select_related('createdby', 'editedby').order_by('process')
    serializer_class = ProcessSerializer
    permission_classes = [IsItemmasterUser]
    search_fields = ['process']


class ColorViewSet(NoDeleteMixin, viewsets.ModelViewSet):
    queryset = Color.objects.order_by('colorname')
    serializer_class = ColorSerializer
    permission_classes = [IsItemmasterUser]
    search_fields = ['colorname', 'pantonecolor']


class ProblemViewSet(NoDeleteMixin, viewsets.ModelViewSet):
    queryset = Problem.objects.order_by('problem')
    serializer_class = ProblemSerializer
    permission_classes = [IsItemmasterUser]
    search_fields = ['problem']


class AttributeMasterViewSet(NoDeleteMixin, viewsets.ModelViewSet):
    queryset = AttributeMaster.objects.order_by('attribute')
    serializer_class = AttributeMasterSerializer
    permission_classes = [IsItemmasterUser]
    search_fields = ['attribute']


class StdParameterViewSet(NoDeleteMixin, viewsets.ModelViewSet):
    queryset = StdParameter.objects.order_by('parameter')
    serializer_class = StdParameterSerializer
    permission_classes = [IsItemmasterUser]
    search_fields = ['parameter']


class MachineViewSet(NoDeleteMixin, viewsets.ModelViewSet):
    queryset = Machine.objects.select_related('user').order_by('machinename')
    serializer_class = MachineSerializer
    permission_classes = [IsItemmasterUser]
    search_fields = ['machinename']


class MachineTaskViewSet(NoDeleteMixin, viewsets.ModelViewSet):
    queryset = MachineTask.objects.select_related('machine').order_by('id')
    serializer_class = MachineTaskSerializer
    permission_classes = [IsItemmasterUser]
    filterset_fields = ['machine']
    search_fields = ['task']


# ---- ItemMaster itself ----------------------------------------------------

class ItemMasterViewSet(NoDeleteMixin, viewsets.ModelViewSet):
    """No delete view ever existed in the old app for this model either —
    items only ever get created, cloned, or edited."""
    queryset = ItemMaster.objects.select_related(
        'itemcustomer', 'pouch_type', 'lami_rubber', 'commodity',
        'cylinder_manufacture', 'createdby', 'editedby',
    )
    serializer_class = ItemMasterSerializer
    permission_classes = [IsItemmasterUser]
    filterset_class = ItemmasterFilter

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        if not can_edit_itemmaster(self.request.user, serializer.instance):
            raise PermissionDenied(
                'Only the item\'s creator, or a user with itemmaster edit rights, can change it.'
            )
        serializer.save(editedby=self.request.user)


# ---- itemmaster sub-resources ---------------------------------------------
# Every write here re-checks can_edit_itemmaster on the PARENT itemmaster —
# in the old app all of these lived behind the single itemmasterdetailedit
# permission check, so an independent REST endpoint has to re-derive that
# same rule per request instead of inheriting it from "which page you're on".

class ItemImageViewSet(viewsets.ModelViewSet):
    queryset = ItemImage.objects.select_related('itemname', 'createdby', 'editedby').order_by('id')
    serializer_class = ItemImageSerializer
    permission_classes = [IsItemmasterUser]
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ['itemname']

    def perform_create(self, serializer):
        itemmaster = serializer.validated_data['itemname']
        if not can_edit_itemmaster(self.request.user, itemmaster):
            raise PermissionDenied('You are not authorized to add images to this item.')
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        if not can_edit_itemmaster(self.request.user, serializer.instance.itemname):
            raise PermissionDenied('You are not authorized to edit images on this item.')
        serializer.save(editedby=self.request.user)

    def perform_destroy(self, instance):
        if not can_edit_itemmaster(self.request.user, instance.itemname):
            raise PermissionDenied('You are not authorized to delete images from this item.')
        instance.delete()


class RawMaterialViewSet(viewsets.ModelViewSet):
    queryset = RawMaterial.objects.select_related(
        'itemmaster', 'materialname', 'item_mat_type', 'item_grade', 'createdby', 'editedby',
    )
    serializer_class = RawMaterialSerializer
    permission_classes = [IsItemmasterUser]
    filterset_fields = ['itemmaster']

    def perform_create(self, serializer):
        itemmaster = serializer.validated_data['itemmaster']
        if not can_edit_itemmaster(self.request.user, itemmaster):
            raise PermissionDenied('You are not authorized to add raw materials to this item.')
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        if not can_edit_itemmaster(self.request.user, serializer.instance.itemmaster):
            raise PermissionDenied('You are not authorized to edit raw materials on this item.')
        serializer.save(editedby=self.request.user)

    def perform_destroy(self, instance):
        if not can_edit_itemmaster(self.request.user, instance.itemmaster):
            raise PermissionDenied('You are not authorized to delete raw materials from this item.')
        itemmaster = instance.itemmaster
        instance.delete()
        # No post_delete signal exists (only post_save) — recalculate here so
        # total_gsm/pouch_weight/pouch_per_kg don't go stale after a delete,
        # a gap the old app had too.
        itemmaster.save()


class ItemProcessViewSet(viewsets.ModelViewSet):
    queryset = ItemProcess.objects.select_related(
        'itemmaster', 'process', 'unit', 'machine', 'createdby', 'editedby',
    )
    serializer_class = ItemProcessSerializer
    permission_classes = [IsItemmasterUser]
    filterset_fields = ['itemmaster']

    def perform_create(self, serializer):
        itemmaster = serializer.validated_data['itemmaster']
        if not can_edit_itemmaster(self.request.user, itemmaster):
            raise PermissionDenied('You are not authorized to add processes to this item.')
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        if not can_edit_itemmaster(self.request.user, serializer.instance.itemmaster):
            raise PermissionDenied('You are not authorized to edit processes on this item.')
        serializer.save(editedby=self.request.user)

    def perform_destroy(self, instance):
        if not can_edit_itemmaster(self.request.user, instance.itemmaster):
            raise PermissionDenied('You are not authorized to delete processes from this item.')
        instance.delete()


class ItemColorViewSet(viewsets.ModelViewSet):
    queryset = ItemColor.objects.select_related('itemmaster', 'color')
    serializer_class = ItemColorSerializer
    permission_classes = [IsItemmasterUser]
    filterset_fields = ['itemmaster']

    def perform_create(self, serializer):
        itemmaster = serializer.validated_data['itemmaster']
        if not can_edit_itemmaster(self.request.user, itemmaster):
            raise PermissionDenied('You are not authorized to add colors to this item.')
        serializer.save()

    def perform_update(self, serializer):
        if not can_edit_itemmaster(self.request.user, serializer.instance.itemmaster):
            raise PermissionDenied('You are not authorized to edit colors on this item.')
        serializer.save()

    def perform_destroy(self, instance):
        if not can_edit_itemmaster(self.request.user, instance.itemmaster):
            raise PermissionDenied('You are not authorized to delete colors from this item.')
        instance.delete()


class ItemAttributeViewSet(viewsets.ModelViewSet):
    queryset = ItemAttribute.objects.select_related('itemmaster', 'item_attirbuate').order_by('id')
    serializer_class = ItemAttributeSerializer
    permission_classes = [IsItemmasterUser]
    filterset_fields = ['itemmaster']

    def perform_create(self, serializer):
        itemmaster = serializer.validated_data['itemmaster']
        if not can_edit_itemmaster(self.request.user, itemmaster):
            raise PermissionDenied('You are not authorized to add attributes to this item.')
        serializer.save()

    def perform_update(self, serializer):
        if not can_edit_itemmaster(self.request.user, serializer.instance.itemmaster):
            raise PermissionDenied('You are not authorized to edit attributes on this item.')
        serializer.save()

    def perform_destroy(self, instance):
        if not can_edit_itemmaster(self.request.user, instance.itemmaster):
            raise PermissionDenied('You are not authorized to delete attributes from this item.')
        instance.delete()


class ItemStandardParameterViewSet(viewsets.ModelViewSet):
    queryset = ItemStandardParameter.objects.select_related('itemmaster', 'standard_parameter').order_by('id')
    serializer_class = ItemStandardParameterSerializer
    permission_classes = [IsItemmasterUser]
    filterset_fields = ['itemmaster']

    def perform_create(self, serializer):
        itemmaster = serializer.validated_data['itemmaster']
        if not can_edit_itemmaster(self.request.user, itemmaster):
            raise PermissionDenied('You are not authorized to add COA parameters to this item.')
        serializer.save()

    def perform_update(self, serializer):
        if not can_edit_itemmaster(self.request.user, serializer.instance.itemmaster):
            raise PermissionDenied('You are not authorized to edit COA parameters on this item.')
        serializer.save()

    def perform_destroy(self, instance):
        if not can_edit_itemmaster(self.request.user, instance.itemmaster):
            raise PermissionDenied('You are not authorized to delete COA parameters from this item.')
        instance.delete()


class CylinderMovementViewSet(NoDeleteMixin, viewsets.ModelViewSet):
    """Soft-delete only, via its own `deleted` flag — matching the model
    (there's no hard-delete view in the old app for this either)."""
    queryset = CylinderMovement.objects.select_related('item', 'location', 'createdby').order_by('-id')
    serializer_class = CylinderMovementSerializer
    permission_classes = [IsItemmasterUser]
    filterset_fields = ['item', 'deleted']

    def perform_create(self, serializer):
        item = serializer.validated_data['item']
        if not can_edit_itemmaster(self.request.user, item):
            raise PermissionDenied('You are not authorized to log cylinder movement for this item.')
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        if not can_edit_itemmaster(self.request.user, serializer.instance.item):
            raise PermissionDenied('You are not authorized to edit cylinder movement for this item.')
        serializer.save()
