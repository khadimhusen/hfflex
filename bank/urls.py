from django.urls import path
from . import views,pdfviews

app_name = 'bank'

urlpatterns = [
    path('list/', views.chequelist, name='chequelist'),
    path('add/', views.chequeadd, name='chequeadd'),
    path('<int:id>/chequeedit/', views.chequeedit, name='chequeedit'),
    path('<int:id>/chequepdf',pdfviews.chequepdf, name='chequepdf'),
    path('<int:id>/a4',pdfviews.a4pdf, name='a4pdf')

]
