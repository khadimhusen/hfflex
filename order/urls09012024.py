from django.urls import path
from . import views, xlviews

app_name = 'order'

urlpatterns = [
    path('orderlist/', views.orderlist, name='orderlist'),
    # 127.0.0.1:8000/order/orderlist/

    path('add/', views.orderadd, name='orderadd'),
    # 127.0.0.1:8000/order/add/

    path('<int:id>/edit/', views.orderedit, name='orderedit'),
    # 127.0.0.1:8000/order/1/edit/

    path('job/<int:id>/detail/', views.jobdetail, name="jobdetail"),
    # 127.0.0.1:8000/order/job/1/detail/

    path('job/<int:id>/print/', views.jobprint, name="jobprint"),
    # 127.0.0.1:8000/order/job/1/detail/

    path('job/<int:id>/edit/', views.jobdetailedit, name="jobdetailedit"),
    # 127.0.0.1:8000/order/job/1/detail/

    path('job/cancel/<int:id>/', views.jobdcancel),
    # 127.0.0.1:8000/order/job/1/detail/

    path('<int:id>/detail/', views.orderdetail, name="orderdetail"),
    # 127.0.0.1:8000/order/1/detail/

    path('detail/edit/<int:id>/', views.orderdetailedit, name='orderdetailedit'),
    # 127.0.0.1:8000/order/detail/edit/1/

    path('joblist/', views.joblist, name='joblist'),
    # 127.0.0.1:8000/order/joblist/

    path('processlist/<str:status>/',views.processlist, name='processlist'),

    path('jobmateriallist/',views.jobmateriallist, name='jobmateriallist'),

    path('ajax/load-address/', views.load_address, name='ajax_load_address'),

    path('process/excel/<str:status>/', xlviews.processlist, name='processexcel'),

    path('job/excel/', xlviews.joblist, name='jobexcel'),

    path('jobmaterail/excel/', xlviews.jobmaterialexcel, name='jobmaterialexcel'),

    path('rate/',views.rate),

    path("alljobtopending",views.unplannedtopending)

]
