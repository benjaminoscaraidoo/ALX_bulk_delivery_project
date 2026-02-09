from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, PackageViewSet

router = DefaultRouter()
router.register(r"orders", OrderViewSet, basename="orders")
router.register(r"packages", PackageViewSet, basename="packages")

urlpatterns = router.urls