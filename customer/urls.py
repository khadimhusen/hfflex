from django.urls import path
from . import views

app_name = 'customer'

urlpatterns = [
    path('list/', views.customerlist, name = 'customerlist'),
    # 127.0.0.1:8000/customer/list/
    path('add/', views.customeradd, name='customeradd'),
    # 127.0.0.1:8000/customer/add/
    path('<int:id>/edit/', views.customeredit, name='customeredit'),
    # 127.0.0.1:8000/customer/1/edit/
    path('<int:id>/detail/', views.customerdetail, name="customerdetail"),
    # 127.0.0.1:8000/customer/1/detail/
    path('detail/add/', views.customerdetailadd, name = 'customerdetailadd'),
    # 127.0.0.1:8000/customer/detail/add/
    path('detail/edit/<int:id>/', views.customerdetailedit, name = 'customerdetailedit'),
    # 127.0.0.1:8000/customer/detail/edit/1/

]

