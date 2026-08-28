from rest_framework.routers import DefaultRouter

from .api_viewsets import PreOrderViewSet, JobNameViewSet, CustomerLookupViewSet, UnitLookupViewSet

router = DefaultRouter()
router.register('customer-lookup', CustomerLookupViewSet, basename='preorder-customer-lookup')
router.register('unit-lookup', UnitLookupViewSet, basename='preorder-unit-lookup')
router.register('preorders', PreOrderViewSet)
router.register('job-names', JobNameViewSet)

urlpatterns = router.urls
