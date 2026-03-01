from django.urls import path
from . import views

app_name = 'manpower'

urlpatterns = [
    path('shiftlist/', views.shiftlist, name='shiftlist'),
    path('newshift/', views.newshift, name='newshift'),
    path('editshift/<int:id>/', views.editshift, name='editshift'),
    path('shiftdetail/<int:id>/', views.shiftdetail, name='shiftdetail'),

]
