from rest_framework.routers import DefaultRouter
from django.urls import path
from .views_dashboard import PersonalDashboardView
from .viewsets import (
    PipelineViewSet, DealStageNameViewSet, DealStageViewSet,
    AccountViewSet, ContactViewSet, DealViewSet,
    DealStageHistoryViewSet, LeadViewSet, CrmUserViewSet,
    NoteViewSet, DealAttachmentViewSet, DealTaskViewSet
)
from .views_dashboard import DealDashboardView, MeView, MyDashboardView, LoginView, LogoutView

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
router.register('deal-tasks', DealTaskViewSet)

urlpatterns = router.urls + [
    path('dashboard/', DealDashboardView.as_view(), name='crm-dashboard'),
    path('me/', MeView.as_view(), name='crm-me'),
    path('login/', LoginView.as_view(), name='crm-login'),
    path('logout/', LogoutView.as_view(), name='crm-logout'),
    path('my-dashboard/', MyDashboardView.as_view(), name='crm-my-dashboard'),
]
