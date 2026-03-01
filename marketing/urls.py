from django.urls import path
from . import views

app_name='marketing'

urlpatterns=[
    path('leadlist/',views.leadlist,name='leadlist'),
    path('leadadd/',views.leadadd,name='leadadd'),
    path('leadedit/<int:id>/',views.leadedit,name='leadedit'),
    path('routelist',views.routelist,name='routelist'),
    path('routeadd',views.routeadd,name='routeadd'),
    path('routeedit/<int:id>/',views.routeedit,name='routeedit'),
    path('visitfeedback/<int:id>/',views.visitfeedback,name='visitfeedback'),
    path('bunchlist',views.bunchlist,name='bunchlist'),
    path('bunchadd',views.bunchadd,name='bunchadd'),
    path('bunchedit/<int:id>/',views.bunchedit,name='bunchedit'),




]