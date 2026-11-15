from rest_framework.routers import DefaultRouter

from .api_viewsets import ActionItemViewSet, MeetingViewSet

router = DefaultRouter()
router.register('meetings', MeetingViewSet, basename='meeting')
router.register('action-items', ActionItemViewSet, basename='meeting-action-item')

urlpatterns = router.urls
