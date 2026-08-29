from rest_framework.routers import DefaultRouter

from .api_viewsets import MachineLookupViewSet, MachineScheduleViewSet

router = DefaultRouter()
router.register('machine-lookup', MachineLookupViewSet, basename='planning-machine-lookup')
router.register('machine-schedules', MachineScheduleViewSet)

urlpatterns = router.urls
