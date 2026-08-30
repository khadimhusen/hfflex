from rest_framework.routers import DefaultRouter

from .api_viewsets import CoaViewSet, TestParameterViewSet, DispatchRegisterLookupViewSet

router = DefaultRouter()
router.register('dispatches', DispatchRegisterLookupViewSet, basename='coa-dispatch')
router.register('coas', CoaViewSet, basename='coa')
router.register('test-parameters', TestParameterViewSet, basename='coa-test-parameter')

urlpatterns = router.urls
