from rest_framework.routers import DefaultRouter

from .api_viewsets import CustomerViewSet, AddressViewSet, PersonViewSet, MarketingUserViewSet

router = DefaultRouter()
router.register('customers', CustomerViewSet)
router.register('addresses', AddressViewSet)
router.register('persons', PersonViewSet)
router.register('marketing-users', MarketingUserViewSet)

urlpatterns = router.urls
