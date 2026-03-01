from django.urls import path
from . import views
from .xlviews import itemlistexcel

app_name = 'itemmaster'

urlpatterns = [
    path('list/', views.itemlist, name='itemlist'),
    # 127.0.0.1:8000/itemmaster/list/

    path('itemlist/',itemlistexcel, name='itemlistexcel'),
    # 127.0.0.1:8000/itemmaster/list/


    path('<int:id>/detail/', views.itemdetail, name='itemdetail'),
    # 127.0.0.1:8000/itemmaster/1/detail/

    path('<int:id>/cylinderdetail/', views.cylinderdetail, name='cylinderdetail'),

    path('add/', views.itemadd, name='itemadd'),
    # 127.0.0.1:8000/itemmaster/add/
    path('detailadd/', views.itemmasterdetailadd, name='itemdetailadd'),
    # 127.0.0.1:8000/itemmaster/detailadd/
    path('<int:id>/detailedit/', views.itemmasterdetailedit, name='itemdetailedit'),
    # 127.0.0.1:8000/itemmaster/1/detailedit/

    path('<int:id>/clone/', views.itemclone, name='itemclone'),
    path('<int:id>/deepclone/', views.deepitemclone, name='deepitemclone'),
    # 127.0.0.1:8000/itemmaster/1/detail/
]
