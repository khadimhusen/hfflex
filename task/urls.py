from django.urls import path
from . import views

app_name = 'task'

urlpatterns = [
    path('list/', views.tasklist, name='tasklist'),
    path('addtask/', views.addtask, name='addtask'),
    path('detail/<int:id>/', views.taskdetail, name='taskdetail'),
    path('requesttoclose/<int:id>/', views.requesttoclosetask, name='requesttoclosetask'),
    path('toclosetask/<int:id>/', views.toclosetask, name='toclosetask'),

]
