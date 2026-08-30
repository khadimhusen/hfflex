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
                  path('marketing/', include("marketing.urls")),
                  path('purchase/', include('purchase.urls')),
                  path('manpower/', include('manpower.urls')),
                  path('quotation/', include('quotation.urls')),
                  path('coa/', include('coa.urls')),
                  path('', views.user_login),
                  path('test/', views.test, name='test'),
                  path('test1/', views.test1, name='test1'),
                  path('test2/', views.test2, name='test2'),
                  path('inkstore/', include('inkstore.urls')),
                  path('documents/', include('documents.urls')),
                  path('ckeditor5/', include('django_ckeditor_5.urls')),
                  path('resolutions/', include('resolutions.urls')),
                  path('permisiondenid/', views.noaccess, name='noaccess'),
                  path('api-auth/', include('rest_framework.urls')),
                  path('returnable/', include('returnable.urls')),
                  path('planning/', include('planning.urls')),
                  path('api/crm/', include('crm.urls')),
                  path('api/customer/', include('customer.api_urls')),
                  path('api/material/', include('material.api_urls')),
                  path('api/itemmaster/', include('itemmaster.api_urls')),
                  path('api/preorder/', include('preorder.api_urls')),
                  path('api/purchase/', include('purchase.api_urls')),
                  path('api/order/', include('order.api_urls')),
                  path('api/production/', include('production.api_urls')),
                  path('api/planning/', include('planning.api_urls')),
                  path('api/manpower/', include('manpower.api_urls')),
                  path('crm/', views.serve_crm_spa, name='crm-spa'),
                  path('crm/<path:path>', views.serve_crm_spa, name='crm-spa-assets'),

              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


# Debug toolbar temporarily disabled (see settings.py) — re-enable both
# together once done.
# if settings.DEBUG:
#     import debug_toolbar
#
#     urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
