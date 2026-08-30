from rest_framework.routers import DefaultRouter

from .api_viewsets import ResolutionViewSet, ResolutionDocumentViewSet

router = DefaultRouter()
router.register('resolutions', ResolutionViewSet, basename='resolution')
router.register('resolution-documents', ResolutionDocumentViewSet, basename='resolution-document')

urlpatterns = router.urls
