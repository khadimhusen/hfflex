from django.urls import path
from . import views

app_name = 'employee'

urlpatterns = [

    path('accesslistedit/<int:id>/', views.accesslistedit, name='accesslistedit'),

    path('employeelist/', views.employeelist, name='employeelist'),
    

    path('workerdetail/<int:id>', views.workerdetail, name='workerdetail')
]
