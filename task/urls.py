from django.urls import path
from . import views

app_name = 'task'

urlpatterns = [
    path('list/', views.tasklist, name='tasklist'),
    path('addtask/', views.addtask, name='addtask'),
    path('detail/<int:id>/', views.taskdetail, name='taskdetail'),
    path('requesttoclose/<int:id>/', views.requesttoclosetask, name='requesttoclosetask'),
    path('toclosetask/<int:id>/', views.toclosetask, name='toclosetask'),
    path('message/<int:id>/', views.post_task_message, name='post_task_message'),
    path('notifications/read/', views.mark_notifications_read, name='mark_notifications_read'),
    path('pending-json/', views.pending_tasks_json, name='pending_tasks_json'),
    path('recurring/', views.recurring_task_list, name='recurring_list'),
    path('recurring/add/', views.recurring_task_add, name='recurring_add'),
    path('recurring/edit/<int:id>/', views.recurring_task_edit, name='recurring_edit'),
    path('recurring/toggle/<int:id>/', views.recurring_task_toggle, name='recurring_toggle'),
]
