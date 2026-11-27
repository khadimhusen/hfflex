from rest_framework.routers import DefaultRouter

from .api_viewsets import AttendanceDayViewSet, PunchLogViewSet

router = DefaultRouter()
router.register('punches', PunchLogViewSet, basename='attendance-punch')
router.register('days', AttendanceDayViewSet, basename='attendance-day')

urlpatterns = router.urls
