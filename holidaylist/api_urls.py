from rest_framework.routers import DefaultRouter

from .api_viewsets import HolidayViewSet

router = DefaultRouter()
router.register('holidays', HolidayViewSet, basename='holiday')

urlpatterns = router.urls
