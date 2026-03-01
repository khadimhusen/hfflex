from django.urls import path
from . import views

app_name = 'material'

urlpatterns = [
    path('material/add', views.materialadd, name='materialadd'),
    # 127.0.0.1:8000/material/material/add/
    path('material/edit/<int:id>/', views.materialedit, name='materialedit'),
    # 127.0.0.1:8000/material/material/edit/1/
    path('material/', views.materiallist, name='materiallist'),
    # 127.0.0.1:8000/material/material/

    path('mattype/add/', views.mattypeadd, name='mattypeadd'),
    # 127.0.0.1:8000/material/mattype/add/
    path('mattype/edit/<int:id>/', views.mattypeedit, name='mattypeedit'),
    # 127.0.0.1:8000/material/mattype/edit/1/
    path('mattype/', views.mattypelist, name='mattypelist'),
    # 127.0.0.1:8000/material/mattype/

    path('grade/edit/<int:id>/', views.gradeedit, name='gradeedit'),
    # 127.0.0.1:8000/material/grade/edit/1/
    path('grade/add/', views.gradeadd, name='gradeadd'),
    # 127.0.0.1:8000/material/grade/add/
    path('grade/', views.gradelist, name='gradelist'),
    # 127.0.0.1:8000/material/grade/

]
