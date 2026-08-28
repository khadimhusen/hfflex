from rest_framework.routers import DefaultRouter

from .api_viewsets import (
    MaterialViewSet, MatTypeViewSet, GradeViewSet, UnitViewSet,
    CommodityViewSet, PurchaseMaterialViewSet,
)

router = DefaultRouter()
router.register('materials', MaterialViewSet)
router.register('mat-types', MatTypeViewSet)
router.register('grades', GradeViewSet)
router.register('units', UnitViewSet)
router.register('commodities', CommodityViewSet)
router.register('purchase-materials', PurchaseMaterialViewSet)

urlpatterns = router.urls
