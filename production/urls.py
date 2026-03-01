from django.urls import path
from . import views, xlviews

app_name = 'production'

urlpatterns = [
    path('inwardlist/', views.inwardlist, name='inwardlist'),
    path('inward/<int:id>/', views.inwarddetail, name='inwarddetail'),
    path('inward/add/', views.inwardadd, name='inwardadd'),
    path('inward/edit/<int:id>/', views.inwardedit, name='inwardedit'),

    path('productionedit/edit/<int:id>/', views.prodreportedit, name='prodreportedit'),
    path('productionedit/edit/<int:id>/addinput/', views.prodreportaddinput, name='prodreportaddinput'),
    path('productionedit/addinputhtmx/<int:id>/', views.addinputhtmx, name='addinputhtmx'),
    path('productionedit/edit/<int:id>/addoutput/', views.prodreportaddoutput, name='prodreportaddoutput'),
    path('productionedit/addoutputhtmx/<int:id>/', views.addoutputhtmx, name='addoutputhtmx'),
    path('productionedit/edit/<int:id>/addperson/', views.prodreportaddperson, name='prodreportaddperson'),
    path('productionedit/addpersonhtmx/<int:id>/', views.addpersonhtmx, name='addpersonhtmx'),
    path('productionedit/addjobqchtmx/<int:id>/', views.addjobqchtmx, name='addjobqchtmx'),
    path('productionedit/edit/<int:id>/addproblem/', views.prodreportaddproblem, name='prodreportaddproblem'),
    path('productionedit/addproblemhtmx/<int:id>/', views.addproblemhtmx, name='addproblemhtmx'),

    path('productionedit/detail/<int:id>/', views.prodreportdetail, name='prodreportdetail'),
    path('inputedit/<int:id>/', views.prodreporteditinput, name='prodreporteditinput'),
    path('outputedit/<int:id>/', views.prodreporteditoutput, name='prodreporteditoutput'),



    path('stocklist/', views.stocklist, name='stocklist'),
    path('stock/<int:id>/', views.singlemaaterialedit, name='singlematerailedit'),


    path('newreport/add/', views.addprodreport, name='addprodreport'),
    path('prodreportlist/<str:status>/', views.prodreportlist, name='prodreportlist'),
    path('jobmaterialstatus/edit/<int:id>/', views.jobmaterialstatusedit, name='jobmaterialstatusedit'),
    path('dispatch/add/', views.dispatchadd, name='dispatchadd'),
    path('dispatch/list/', views.dispatchlist, name='dispatchlist'),
    path('dispatch/pending/', views.dispatchpending, name='dispatchpending'),
    path('dispatch/approvalpending/', views.dispatchapprovalpending, name='dispatchapprovalpending'),
    path('dispatch/dispatchapproval/<int:id>/', views.dispatchapproval, name='dispatchapproval'),
    path('dispatch/edit/<int:id>/', views.dispatchdetailedit, name='dispatchdetailedit'),
    path('dispatch/detail/<int:id>/', views.dispatchdetail, name='dispatchdetail'),
    path('stock/excel/', xlviews.stocklist, name='stockexcel'),

    path('changevalue/', views.changevalue ),
    path('stocktest/<int:id>/',views.stockdetail),

    path('dispatch/lock/<int:id>/', views.dispatchlock, name='dispatchlock'),
    path('dispatch/unlock/<int:id>/', views.dispatchunlock, name='dispatchunlock')
]
