from django.urls import path
from . import views , pdfviews

app_name = 'quotation'

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
    path('letterheadquotepdf/<int:id>/',pdfviews.letterheadquotepdf,name='letterheadquotepdf'),
    path('quoteapproval/<int:id>/',views.quoteapproval,name='quoteapproval'),


]
