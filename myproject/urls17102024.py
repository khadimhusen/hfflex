from django.contrib import admin
from django.urls import path, include
from . import views
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
                  path('admin/', admin.site.urls),
                  path('login/', views.user_login, name='home'),
                  path('logout/', views.user_logout, name='logout'),
                  path('customer/', include('customer.urls')),
                  path('itemmaster/', include('itemmaster.urls')),
                  path('production/', include('production.urls')),
                  path('employee/', include('employee.urls')),
		  path('bank/', include("bank.urls")),
		  path('order/', include('order.urls')),
                  path('preorder/', include('preorder.urls')),
                  path('material/', include('material.urls')),
		  path('quality/', include("quality.urls")),
		  path('purchase/', include('purchase.urls')),
                  path('quotation/',include('quotation.urls')),
                  path('manpower/', include('manpower.urls')),
                  path('', views.user_login),
                  path('test/<int:start>/<int:end>/', views.test, name='test'),
                  path('permisiondenid/', views.noaccess, name='noaccess'),


              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
