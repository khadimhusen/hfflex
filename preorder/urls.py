from django.urls import path
from . import views

app_name = 'preorder'

urlpatterns=[
    path('',views.preorderlist, name='preorderlist'),
    path('preorderpending/',views.preorderpendinglist, name='preorderpendinglist'),
    path('add/',views.addpreorder,name='addpreorder'),
    path('editpreorder/<int:id>/',views.editpreorder,name='editpreorder'),
    path('editpreorderfinal/<int:id>/',views.finalsubmit,name='finalsubmit'),
             ]