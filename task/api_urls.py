from rest_framework.routers import DefaultRouter

from .api_viewsets import NotificationViewSet, TaskViewSet, UserLookupViewSet

router = DefaultRouter()
router.register('user-lookup', UserLookupViewSet, basename='task-user-lookup')
router.register('tasks', TaskViewSet)
router.register('notifications', NotificationViewSet, basename='task-notification')

urlpatterns = router.urls
