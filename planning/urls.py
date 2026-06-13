from django.urls import path
from . import views

app_name = 'planning'

urlpatterns = [
    path('machine/<int:machine_id>/schedule/',
         views.machine_schedule, name='machine_schedule'),

    path('machine/<int:machine_id>/schedule/reorder/',
         views.reorder_queue, name='reorder_queue'),

    path('machine/<int:machine_id>/schedule/add-idle/',
         views.add_idle_slot, name='add_idle_slot'),

    path('machine/<int:machine_id>/schedule/idle/<int:schedule_id>/edit/',
         views.edit_idle_slot, name='edit_idle_slot'),

    path('machine/<int:machine_id>/schedule/idle/<int:schedule_id>/delete/',
         views.delete_idle_slot, name='delete_idle_slot'),

    path('machine/<int:machine_id>/schedule/<int:schedule_id>/edit/',
         views.edit_schedule, name='edit_schedule'),

    path('machine/<int:machine_id>/schedule/<int:schedule_id>/tasks/',
         views.schedule_tasks, name='schedule_tasks'),

    path('machine/<int:machine_id>/schedule/<int:schedule_id>/start/',
         views.start_schedule, name='start_schedule'),

    path('machine/<int:machine_id>/schedule/<int:schedule_id>/complete/',
         views.complete_schedule, name='complete_schedule'),

    path('machine/<int:machine_id>/schedule/<int:schedule_id>/downtime/',
         views.add_downtime, name='add_downtime'),
    
]
