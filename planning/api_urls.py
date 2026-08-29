from django.urls import path
from rest_framework.routers import DefaultRouter

from .api_viewsets import (
    MachineLookupViewSet, IdleTimeLookupViewSet, MachineScheduleViewSet,
    MachineBoardView, ReorderQueueView, AddIdleSlotView,
)

router = DefaultRouter()
router.register('machine-lookup', MachineLookupViewSet, basename='planning-machine-lookup')
router.register('idletime-lookup', IdleTimeLookupViewSet, basename='planning-idletime-lookup')
router.register('machine-schedules', MachineScheduleViewSet)

urlpatterns = [
    path('machines/<int:machine_id>/board/', MachineBoardView.as_view(), name='planning-machine-board'),
    path('machines/<int:machine_id>/reorder/', ReorderQueueView.as_view(), name='planning-reorder-queue'),
    path('machines/<int:machine_id>/add-idle/', AddIdleSlotView.as_view(), name='planning-add-idle'),
] + router.urls
