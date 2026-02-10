from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, PackageViewSet
from django.urls import path, include

#router = DefaultRouter()
#router.register(r"orders", OrderViewSet, basename="orders")
#router.register(r"packages", PackageViewSet, basename="packages")

urlpatterns = [
#path('', include(router.urls)),
]