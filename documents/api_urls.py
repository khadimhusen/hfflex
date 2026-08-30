from rest_framework.routers import DefaultRouter

from .api_viewsets import DocumentViewSet, UserLookupViewSet

router = DefaultRouter()
router.register('user-lookup', UserLookupViewSet, basename='documents-user-lookup')
router.register('documents', DocumentViewSet, basename='document')

urlpatterns = router.urls
