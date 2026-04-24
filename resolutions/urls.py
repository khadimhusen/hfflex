from django.urls import path
from . import views

app_name="resolutions"

urlpatterns = [
    path('', views.resolution_list, name='resolution_list'),
    path('create/', views.resolution_create, name='resolution_create'),
    path('<int:pk>/', views.resolution_detail, name='resolution_detail'),
    path('<int:pk>/edit/', views.resolution_edit, name='resolution_edit'),
    path('<int:pk>/delete/', views.resolution_delete, name='resolution_delete'),
]