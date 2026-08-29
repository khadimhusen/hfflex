from django.urls import path
from rest_framework.routers import DefaultRouter

from .api_viewsets import (
    SupplierLookupViewSet, CustomerLookupViewSet, AddressLookupViewSet, WorkerLookupViewSet,
    ProblemLookupViewSet, QcTestLookupViewSet, ProductionProblemLookupViewSet,
    MaterialLookupViewSet, MatTypeLookupViewSet, GradeLookupViewSet, UnitLookupViewSet,
    SupervisorLookupViewSet, JobProcessLookupViewSet, ProdInputMaterialLookupViewSet,
    InwardViewSet, InwardStockViewSet,
    ProdReportViewSet, ProdInputViewSet, ProdOutputViewSet, ProdPersonViewSet, ProdProblemViewSet, JobQcViewSet,
    StockdetailReportViewSet, StockdetailEditViewSet, ProblemTagViewSet,
    DispatchRegisterViewSet, OtherDispatchItemViewSet, DispatchableStockViewSet,
    DispatchPendingView, DispatchApprovalPendingView, DispatchApprovalView,
)

router = DefaultRouter()
router.register('supplier-lookup', SupplierLookupViewSet, basename='production-supplier-lookup')
router.register('customer-lookup', CustomerLookupViewSet, basename='production-customer-lookup')
router.register('address-lookup', AddressLookupViewSet, basename='production-address-lookup')
router.register('worker-lookup', WorkerLookupViewSet, basename='production-worker-lookup')
router.register('problem-lookup', ProblemLookupViewSet, basename='production-problem-lookup')
router.register('qctest-lookup', QcTestLookupViewSet, basename='production-qctest-lookup')
router.register('production-problem-lookup', ProductionProblemLookupViewSet, basename='production-productionproblem-lookup')
router.register('material-lookup', MaterialLookupViewSet, basename='production-material-lookup')
router.register('mattype-lookup', MatTypeLookupViewSet, basename='production-mattype-lookup')
router.register('grade-lookup', GradeLookupViewSet, basename='production-grade-lookup')
router.register('unit-lookup', UnitLookupViewSet, basename='production-unit-lookup')
router.register('supervisor-lookup', SupervisorLookupViewSet, basename='production-supervisor-lookup')
router.register('jobprocess-lookup', JobProcessLookupViewSet, basename='production-jobprocess-lookup')
router.register('prodinput-material-lookup', ProdInputMaterialLookupViewSet, basename='production-prodinput-material-lookup')

router.register('inwards', InwardViewSet)
router.register('inward-stock', InwardStockViewSet, basename='production-inward-stock')

router.register('prodreports', ProdReportViewSet)
router.register('prodinputs', ProdInputViewSet)
router.register('prodoutputs', ProdOutputViewSet, basename='production-prodoutputs')
router.register('prodpersons', ProdPersonViewSet)
router.register('prodproblems', ProdProblemViewSet)
router.register('jobqcs', JobQcViewSet)

router.register('stock-report', StockdetailReportViewSet, basename='production-stock-report')
router.register('stock-edit', StockdetailEditViewSet, basename='production-stock-edit')
router.register('problem-tags', ProblemTagViewSet)

router.register('dispatches', DispatchRegisterViewSet)
router.register('dispatch-items', OtherDispatchItemViewSet)
router.register('dispatchable-stock', DispatchableStockViewSet, basename='production-dispatchable-stock')

urlpatterns = router.urls + [
    path('dispatch-pending/', DispatchPendingView.as_view(), name='production-dispatch-pending'),
    path('dispatch-approval-pending/', DispatchApprovalPendingView.as_view(), name='production-dispatch-approval-pending'),
    path('dispatch-approval/<int:pk>/', DispatchApprovalView.as_view(), name='production-dispatch-approval'),
]
