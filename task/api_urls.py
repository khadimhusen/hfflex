from django.urls import path
from rest_framework.routers import DefaultRouter

from .api_review import LaterView, ReviewView
from .api_viewsets import (
    NotificationViewSet, RecurringTaskViewSet, TaskMsgViewSet, TaskViewSet, UserLookupViewSet,
)

router = DefaultRouter()
router.register('user-lookup', UserLookupViewSet, basename='task-user-lookup')
router.register('tasks', TaskViewSet)
router.register('notifications', NotificationViewSet, basename='task-notification')
router.register('task-messages', TaskMsgViewSet, basename='task-message')
router.register('recurring-tasks', RecurringTaskViewSet, basename='recurring-task')

urlpatterns = [
    path('review/', ReviewView.as_view(), name='task-review'),
    path('review/later/<int:pk>/', LaterView.as_view(), name='task-review-later'),
] + router.urls
