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
                  path('task/', include("task.urls")),
                  path('order/', include('order.urls')),
                  path('preorder/', include('preorder.urls')),
                  path('material/', include('material.urls')),
                  path('quality/', include("quality.urls")),
                  path('marketing/',include("marketing.urls")),
                  path('purchase/', include('purchase.urls')),
                  path('manpower/', include('manpower.urls')),
                  path('quotation/', include('quotation.urls')),
                  path('', views.user_login),
                  path('test/', views.test, name='test'),
                  path('permisiondenid/', views.noaccess, name='noaccess'),
                  path('api-auth/', include('rest_framework.urls')),
                  path('returnable/', include('returnable.urls')),

              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
