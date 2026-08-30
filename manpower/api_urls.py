from rest_framework.routers import DefaultRouter

from .api_viewsets import (
    MachineLookupViewSet, WorkerLookupViewSet, ProblemLookupViewSet,
    ShiftViewSet, ActivityViewSet, ShiftPersonViewSet, DowntimeReportViewSet,
)

router = DefaultRouter()
router.register('machine-lookup', MachineLookupViewSet, basename='manpower-machine-lookup')
router.register('worker-lookup', WorkerLookupViewSet, basename='manpower-worker-lookup')
router.register('problem-lookup', ProblemLookupViewSet, basename='manpower-problem-lookup')
router.register('shifts', ShiftViewSet)
router.register('activities', ActivityViewSet)
router.register('shift-persons', ShiftPersonViewSet)
router.register('downtimes', DowntimeReportViewSet)

urlpatterns = router.urls
