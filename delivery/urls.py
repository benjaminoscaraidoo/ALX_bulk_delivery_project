from rest_framework.routers import DefaultRouter
from .views import DeliveryViewSet,PaymentViewSet
from django.urls import path, include

#router = DefaultRouter()
#router.register(r"deliveries", DeliveryViewSet, basename="deliveries")
#router.register(r"payments", PaymentViewSet, basename="payments")

urlpatterns = [
#path('', include(router.urls)),
]