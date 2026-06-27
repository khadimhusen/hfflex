from django.urls import path
from . import views

app_name = 'inkstore'

urlpatterns = [
    path('',        views.ink_list,  name='list'),
    path('search/', views.search_ink, name='search'),
    path('<int:pk>/edit/', views.edit_ink, name='edit'),
]