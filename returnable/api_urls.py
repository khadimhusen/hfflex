from rest_framework.routers import DefaultRouter

from .api_viewsets import (
    CustomerLookupViewSet, AddressLookupViewSet, UnitLookupViewSet,
    ReturnableViewSet, ChallanItemViewSet, ReceivedChallanViewSet, ReceivedItemViewSet,
)

router = DefaultRouter()
router.register('customers', CustomerLookupViewSet, basename='returnable-customer')
router.register('addresses', AddressLookupViewSet, basename='returnable-address')
router.register('units', UnitLookupViewSet, basename='returnable-unit')
router.register('challans', ReturnableViewSet, basename='returnable-challan')
router.register('challan-items', ChallanItemViewSet, basename='returnable-challan-item')
router.register('received-challans', ReceivedChallanViewSet, basename='returnable-received-challan')
router.register('received-items', ReceivedItemViewSet, basename='returnable-received-item')

urlpatterns = router.urls
