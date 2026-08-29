from django.urls import path
from rest_framework.routers import DefaultRouter

from .api_viewsets import (
    OrderViewSet, JobViewSet,
    CustomerLookupViewSet, AddressLookupViewSet, MarketingPersonLookupViewSet,
    UnitLookupViewSet, ItemMasterLookupViewSet, PrejobLookupViewSet,
    MaterialLookupViewSet, MatTypeLookupViewSet, GradeLookupViewSet, ProcessLookupViewSet,
    ColorLookupViewSet, AttributeMasterLookupViewSet, StdParameterLookupViewSet,
    PouchTypeLookupViewSet, LamiRubberLookupViewSet,
    JobMaterialViewSet, JobProcessViewSet, JobColorViewSet, JobImageViewSet,
    JobItemAttributeViewSet, JobCoaViewSet,
    ProcessReportViewSet, JobMaterialReportViewSet, JobChangeLogViewSet,
    BulkMaterialRateView, AssignMarketingPersonView, GetMarketingPersonView,
    StockdetailLookupViewSet, JobMaterialStatusViewSet,
)

router = DefaultRouter()
router.register('customer-lookup', CustomerLookupViewSet, basename='order-customer-lookup')
router.register('address-lookup', AddressLookupViewSet, basename='order-address-lookup')
router.register('marketing-person-lookup', MarketingPersonLookupViewSet, basename='order-marketing-person-lookup')
router.register('unit-lookup', UnitLookupViewSet, basename='order-unit-lookup')
router.register('itemmaster-lookup', ItemMasterLookupViewSet, basename='order-itemmaster-lookup')
router.register('prejob-lookup', PrejobLookupViewSet, basename='order-prejob-lookup')
router.register('material-lookup', MaterialLookupViewSet, basename='order-material-lookup')
router.register('mattype-lookup', MatTypeLookupViewSet, basename='order-mattype-lookup')
router.register('grade-lookup', GradeLookupViewSet, basename='order-grade-lookup')
router.register('process-lookup', ProcessLookupViewSet, basename='order-process-lookup')
router.register('color-lookup', ColorLookupViewSet, basename='order-color-lookup')
router.register('attribute-lookup', AttributeMasterLookupViewSet, basename='order-attribute-lookup')
router.register('stdparameter-lookup', StdParameterLookupViewSet, basename='order-stdparameter-lookup')
router.register('pouchtype-lookup', PouchTypeLookupViewSet, basename='order-pouchtype-lookup')
router.register('lamirubber-lookup', LamiRubberLookupViewSet, basename='order-lamirubber-lookup')
router.register('orders', OrderViewSet)
router.register('jobs', JobViewSet)
router.register('job-materials', JobMaterialViewSet)
router.register('job-processes', JobProcessViewSet)
router.register('job-colors', JobColorViewSet)
router.register('job-images', JobImageViewSet)
router.register('job-attributes', JobItemAttributeViewSet)
router.register('job-coas', JobCoaViewSet)
router.register('process-report', ProcessReportViewSet, basename='order-process-report')
router.register('job-material-report', JobMaterialReportViewSet, basename='order-job-material-report')
router.register('job-change-log', JobChangeLogViewSet, basename='order-job-change-log')
router.register('stockdetail-lookup', StockdetailLookupViewSet, basename='order-stockdetail-lookup')
router.register('job-material-status', JobMaterialStatusViewSet)

urlpatterns = router.urls + [
    path('bulk-material-rate/', BulkMaterialRateView.as_view(), name='order-bulk-material-rate'),
    path('assign-marketing-person/', AssignMarketingPersonView.as_view(), name='order-assign-marketing-person'),
    path('get-marketing-person/', GetMarketingPersonView.as_view(), name='order-get-marketing-person'),
]
