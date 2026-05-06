from django.urls import path
from . import views

app_name = 'coa'


urlpatterns = [
    path('new/<int:jobid>/', views.addcoa, name='addcoa'),
    path('newcoadc/<int:jobid>/<int:dcid>/', views.addcoa, name='addcoadc'),
    path('coaedit/<int:id>', views.coaedit, name='coaedit'),
    path('coadetail/<int:pk>', views.coadetail, name='coadetail'),
    path('coaapprove/<int:pk>', views.coaapprove, name='coaaprove'),
]
