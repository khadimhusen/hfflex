from django.urls import path
from . import views, pdfviews, xlviews

app_name = 'purchase'

urlpatterns = [
    path('purchaselist/', views.purchaselist, name='purchaselist'),
    # 127.0.0.1:8000/purchase/purchaselist/

    path('xlpurchaselist/', xlviews.xlpolist, name='xlpurchaselist'),

    path('purchasenew/', views.purchasenew, name='purchasenew'),
    # 127.0.0.1:8000/purchase/purchasenew/

    path('purchaseedit/<int:id>/', views.purchaseedit, name='purchaseedit'),
    # 127.0.0.1:8000/purchase/purchaseedit/1/

    path('purchasedetail/<int:id>/', views.purchasedetail, name='purchasedetail'),
    # 127.0.0.1:8000/purchase/purchasedetail/1/

    path('deepclone/<int:id>/', views.deepclonepurchase, name='deepclonepurchase'),

    path('purchasepdf/<int:id>', pdfviews.newpopdf, name="popdf"),
    # 127.0.0.1:8000/purchase/purcahsepdf/1/

    path('poapproval/<int:id>/', views.poapproval, name="poapproval"),

    path('removepoapproval/<int:id>/', views.removepoapproval, name="removepoapproval"),

    path('purchase/poimageadd/<int:id>/', views.addpoimage, name='addpoimage'),

    path('purchase/poexpeteddate/<int:id>/', views.poexpeteddate, name='poexpeteddate'),

    path('purchase/itemlist/', views.poitemlist, name='poitemlist'),

    path('purchase/xlitemlist/', xlviews.xlpoitemlist, name='xlpoitemlist'),

    path('testing/', views.some_view, name="someview"),

    path('setcategory/', views.setcatogery),

]
