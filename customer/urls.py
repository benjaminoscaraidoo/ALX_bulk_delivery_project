from rest_framework.routers import DefaultRouter
from .views import CustomerProfileViewSet, DriverProfileViewSet

router = DefaultRouter()
router.register(r"profiles/customer", CustomerProfileViewSet, basename="customer-profile")
router.register(r"profiles/driver", DriverProfileViewSet, basename="driver-profile")

urlpatterns = router.urls