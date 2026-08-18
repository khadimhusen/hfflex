from rest_framework.routers import DefaultRouter
from django.urls import path
from .views_dashboard import PersonalDashboardView
from .viewsets import (
    PipelineViewSet, DealStageNameViewSet, DealStageViewSet,
    AccountViewSet, ContactViewSet, DealViewSet,
    DealStageHistoryViewSet, LeadViewSet, CrmUserViewSet,
    NoteViewSet, DealAttachmentViewSet
)
from .views_dashboard import DealDashboardView, MeView, MyDashboardView

router = DefaultRouter()
router.register('pipelines', PipelineViewSet)
router.register('stage-names', DealStageNameViewSet)
router.register('stages', DealStageViewSet)
router.register('accounts', AccountViewSet)
router.register('contacts', ContactViewSet)
router.register('deals', DealViewSet)
router.register('deal-stage-history', DealStageHistoryViewSet)
router.register('leads', LeadViewSet)
router.register('users', CrmUserViewSet)
router.register('notes', NoteViewSet)
router.register('deal-attachments', DealAttachmentViewSet)

urlpatterns = router.urls + [
    path('dashboard/', DealDashboardView.as_view(), name='crm-dashboard'),
    path('me/', MeView.as_view(), name='crm-me'),
    path('my-dashboard/', MyDashboardView.as_view(), name='crm-my-dashboard'),
]
