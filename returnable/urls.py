from django.urls import path
from . import views, pdfviews

app_name = 'returnable'

urlpatterns = [
    path('returnablelist/', views.returnablelist, name='returnablelist'),
    # 127.0.0.1:8000/returnable/returnablelist/

    path('returnablenew/', views.returnablenew, name='returnablenew'),
    # 127.0.0.1:8000/returnable/returnableenewenew/

    path('returnableedit/<int:id>/', views.returnableedit, name='returnableedit'),
    # 127.0.0.1:8000/returnable/returnableedit/1/

    path('ajax/load-address/', views.load_address, name='ajax_load_address'),

    path('returnabledetail/<int:id>/', views.returnabledetail, name='returnabledetail'),

    path('receivedchallannew/', views.receivedchallannew, name='receivedchallannew'),

    path('r_c_edit/<int:id>/', views.r_c_edit, name='r_c_edit'),

    path('receivedlist/', views.receivedlist, name='receivedlist'),

    path('challanitemlist/', views.challanitemlist, name='challanitemlist'),
    # 127.0.0.1:8000/returnable/challanitemlist/

    path('returnable-pdf/<int:id>/', pdfviews.returnable_pdf, name='returnable_pdf'),
]
