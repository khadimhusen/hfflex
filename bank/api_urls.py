from django.urls import path
from rest_framework.routers import DefaultRouter

from .api_viewsets import BankLookupViewSet, BankViewSet, ChequeViewSet, PartyLookupView

router = DefaultRouter()
router.register('bank-lookup', BankLookupViewSet, basename='bank-lookup')
router.register('banks', BankViewSet)
router.register('cheques', ChequeViewSet)

urlpatterns = [
    path('party-lookup/', PartyLookupView.as_view(), name='bank-party-lookup'),
] + router.urls
