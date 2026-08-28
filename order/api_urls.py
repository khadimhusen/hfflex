from rest_framework.routers import DefaultRouter

from .api_viewsets import (
    OrderViewSet, JobViewSet,
    CustomerLookupViewSet, AddressLookupViewSet, MarketingPersonLookupViewSet,
    UnitLookupViewSet, ItemMasterLookupViewSet, PrejobLookupViewSet,
)

router = DefaultRouter()
router.register('customer-lookup', CustomerLookupViewSet, basename='order-customer-lookup')
router.register('address-lookup', AddressLookupViewSet, basename='order-address-lookup')
router.register('marketing-person-lookup', MarketingPersonLookupViewSet, basename='order-marketing-person-lookup')
router.register('unit-lookup', UnitLookupViewSet, basename='order-unit-lookup')
router.register('itemmaster-lookup', ItemMasterLookupViewSet, basename='order-itemmaster-lookup')
router.register('prejob-lookup', PrejobLookupViewSet, basename='order-prejob-lookup')
router.register('orders', OrderViewSet)
router.register('jobs', JobViewSet)

urlpatterns = router.urls
