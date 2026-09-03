from rest_framework.routers import DefaultRouter

from .api_viewsets import (
    CustomerViewSet, AddressViewSet, PersonViewSet, MarketingUserViewSet, PincodeViewSet,
)

router = DefaultRouter()
router.register('customers', CustomerViewSet)
router.register('addresses', AddressViewSet)
router.register('persons', PersonViewSet)
router.register('marketing-users', MarketingUserViewSet)
router.register('pincodes', PincodeViewSet)

urlpatterns = router.urls
