from rest_framework.routers import DefaultRouter

from .api_viewsets import (
    PoViewSet, PoItemViewSet, PoImageViewSet, ExpectedDateViewSet,
    SupplierLookupViewSet, ShipToLookupViewSet, DeliveryAddressLookupViewSet,
    UnitLookupViewSet, TermLookupViewSet,
)

router = DefaultRouter()
router.register('supplier-lookup', SupplierLookupViewSet, basename='purchase-supplier-lookup')
router.register('ship-to-lookup', ShipToLookupViewSet, basename='purchase-ship-to-lookup')
router.register('delivery-address-lookup', DeliveryAddressLookupViewSet, basename='purchase-delivery-address-lookup')
router.register('unit-lookup', UnitLookupViewSet, basename='purchase-unit-lookup')
router.register('term-lookup', TermLookupViewSet, basename='purchase-term-lookup')
router.register('purchase-orders', PoViewSet)
router.register('po-items', PoItemViewSet)
router.register('po-images', PoImageViewSet)
router.register('expected-dates', ExpectedDateViewSet)

urlpatterns = router.urls
