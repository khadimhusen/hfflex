from django.urls import path
from rest_framework.routers import DefaultRouter

from .api_viewsets import CandidateViewSet, InterviewViewSet, JobOpeningViewSet, summary

router = DefaultRouter()
router.register('openings', JobOpeningViewSet, basename='recruitment-opening')
router.register('candidates', CandidateViewSet, basename='recruitment-candidate')
router.register('interviews', InterviewViewSet, basename='recruitment-interview')

urlpatterns = [path('summary/', summary, name='recruitment-summary')] + router.urls
