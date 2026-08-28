from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Commodity, Material, MatType, Grade, Unit, PurchaseMaterial
from .api_serializers import (
    CommoditySerializer, MaterialSerializer, MatTypeSerializer,
    GradeSerializer, UnitSerializer, PurchaseMaterialSerializer,
)


class StampedCreateUpdateMixin:
    """Material/MatType/Grade/Unit all stamp createdby/editedby the same way."""

    def perform_create(self, serializer):
        serializer.save(createdby=self.request.user)

    def perform_update(self, serializer):
        serializer.save(editedby=self.request.user)


# No dedicated department flag ever gated this app in the old system —
# @accessview there is a no-op, so any authenticated user already has
# real access today. IsAuthenticated here matches that, rather than
# inheriting the global IsCrmUser default these endpoints have nothing
# to do with.
class MaterialViewSet(StampedCreateUpdateMixin, viewsets.ModelViewSet):
    queryset = Material.objects.select_related('createdby', 'editedby').order_by('name')
    serializer_class = MaterialSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['name']


class MatTypeViewSet(StampedCreateUpdateMixin, viewsets.ModelViewSet):
    queryset = MatType.objects.select_related('createdby', 'editedby').order_by('mat_type')
    serializer_class = MatTypeSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['mat_type']


class GradeViewSet(StampedCreateUpdateMixin, viewsets.ModelViewSet):
    queryset = Grade.objects.select_related('createdby', 'editedby').order_by('grade')
    serializer_class = GradeSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['grade']


class UnitViewSet(StampedCreateUpdateMixin, viewsets.ModelViewSet):
    queryset = Unit.objects.select_related('createdby', 'editedby').order_by('unit')
    serializer_class = UnitSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['unit']


class CommodityViewSet(viewsets.ModelViewSet):
    queryset = Commodity.objects.order_by('commodity')
    serializer_class = CommoditySerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['commodity']


class PurchaseMaterialViewSet(viewsets.ModelViewSet):
    queryset = PurchaseMaterial.objects.order_by('itemname')
    serializer_class = PurchaseMaterialSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['itemname']
