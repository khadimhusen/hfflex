from django.urls import path
from . import views

app_name = 'employee'

urlpatterns = [

    path('accesslistedit/<int:id>/', views.accesslistedit, name='accesslistedit'),

    path('employeelist/', views.employeelist, name='employeelist'),

    path('workerdetail/<int:id>', views.workerdetail, name='workerdetail'),

    path('assets/', views.asset_list, name='asset_list'),
    path('assets/create/', views.asset_create, name='asset_create'),
    path('assets/<int:pk>/', views.asset_detail, name='asset_detail'),
    path('assets/<int:pk>/edit/', views.asset_update, name='asset_update'),
    path('assets/<int:pk>/dispose/', views.asset_dispose, name='asset_dispose'),

    path('assignments/', views.assignment_list, name='assignment_list'),
    path('assignments/issue/', views.asset_issue, name='asset_issue'),
    path('assignments/<int:pk>/return/', views.asset_return, name='asset_return'),
    path('employees/<int:employee_id>/assets/', views.employee_asset_detail, name='employee_asset_detail'),
]
