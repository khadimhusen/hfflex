from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views , pdfviews
from .viewsets import QuotationViewSet, TermViewSet

app_name = 'quotation'

router = DefaultRouter()
router.register('quotations', QuotationViewSet, basename='quotation')
router.register('terms', TermViewSet)

urlpatterns = [
    path('costing/', views.costing, name='costing'),
    path('addnew/', views.addquotation, name='addquotation'),
    path('edit/<int:id>/', views.editquote, name='editquote'),
    path('detail/<int:id>/', views.detailquote, name='quotationdetail'),
    path('list/', views.quotationlist, name='quotationlist'),
    path('materialjson/',views.materialjson,name='materialjson'),
    path('getstructure/<str:ply>/',views.getstructurejson),
    path('getquotationjson/',views.getquotationjson),
    path('quotepdf/<int:id>/',pdfviews.quotepdf,name='quotepdf'),
    path('quotepdf-v2/<int:id>/',pdfviews.quotepdf_v2,name='quotepdf-v2'),
    path('letterheadquotepdf/<int:id>/',pdfviews.letterheadquotepdf,name='letterheadquotepdf'),
    path('quoteapproval/<int:id>/',views.quoteapproval,name='quoteapproval'),
    path('copy/<int:id>/', views.copyquote, name='copyquote'),


] + router.urls
