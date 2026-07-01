from django.urls import path
from . import views

app_name = 'coa'


urlpatterns = [
    path('new/<int:jobid>/', views.add_coa, name='addcoa'),
    path('newcoadc/<int:jobid>/<int:dcid>/', views.add_coa, name='addcoadc'),
    path('coaedit/<int:id>', views.coa_edit, name='coaedit'),
    path('coadetail/<int:pk>', views.coa_detail, name='coadetail'),
    path('coaapprove/<int:pk>', views.coa_approve, name='coaaprove'),
    path('coareopen/<int:pk>', views.coa_reopen, name='coa_reopen'),
]
