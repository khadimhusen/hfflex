from django.urls import path
from rest_framework.routers import DefaultRouter

from .api_viewsets import MixedInkViewSet, InkSearchView

router = DefaultRouter()
router.register('inks', MixedInkViewSet, basename='inkstore-ink')

urlpatterns = router.urls + [
    path('search/', InkSearchView.as_view(), name='inkstore-search'),
]
