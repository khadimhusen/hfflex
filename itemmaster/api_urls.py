from rest_framework.routers import DefaultRouter

from .api_viewsets import (
    MachineViewSet, MachineTaskViewSet, PouchTypeViewSet, LamiRubberViewSet,
    ItemMasterViewSet, ItemImageViewSet, RawMaterialViewSet, ProcessViewSet,
    ItemProcessViewSet, ColorViewSet, ItemColorViewSet, ProblemViewSet,
    AttributeMasterViewSet, ItemAttributeViewSet, CylinderMovementViewSet,
    StdParameterViewSet, ItemStandardParameterViewSet, CustomerLookupViewSet,
    MaterialLookupViewSet, MatTypeLookupViewSet, GradeLookupViewSet, UnitLookupViewSet,
    CommodityLookupViewSet,
)

router = DefaultRouter()
router.register('customer-lookup', CustomerLookupViewSet, basename='itemmaster-customer-lookup')
router.register('material-lookup', MaterialLookupViewSet, basename='itemmaster-material-lookup')
router.register('mat-type-lookup', MatTypeLookupViewSet, basename='itemmaster-mat-type-lookup')
router.register('grade-lookup', GradeLookupViewSet, basename='itemmaster-grade-lookup')
router.register('unit-lookup', UnitLookupViewSet, basename='itemmaster-unit-lookup')
router.register('commodity-lookup', CommodityLookupViewSet, basename='itemmaster-commodity-lookup')
router.register('items', ItemMasterViewSet)
router.register('raw-materials', RawMaterialViewSet)
router.register('item-images', ItemImageViewSet)
router.register('item-processes', ItemProcessViewSet)
router.register('item-colors', ItemColorViewSet)
router.register('item-attributes', ItemAttributeViewSet)
router.register('item-standard-parameters', ItemStandardParameterViewSet)
router.register('cylinder-movements', CylinderMovementViewSet)
router.register('pouch-types', PouchTypeViewSet)
router.register('lami-rubbers', LamiRubberViewSet)
router.register('processes', ProcessViewSet)
router.register('colors', ColorViewSet)
router.register('problems', ProblemViewSet)
router.register('attribute-masters', AttributeMasterViewSet)
router.register('standard-parameters', StdParameterViewSet)
router.register('machines', MachineViewSet)
router.register('machine-tasks', MachineTaskViewSet)

urlpatterns = router.urls
