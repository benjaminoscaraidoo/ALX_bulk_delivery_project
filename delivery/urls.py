from rest_framework.routers import DefaultRouter
from .views import add_deliveries,CreateDeliveriesAPIView,DriverDeliveryUpdateAPIView
from django.urls import path, include

app_name = "delivery"

urlpatterns = [
    path("add/<int:order_id>/", add_deliveries, name="add_deliveries"),
    path("api/v1/create/",CreateDeliveriesAPIView.as_view(),name="create_deliveries"),
    path("api/v1/updatedelivery/",DriverDeliveryUpdateAPIView.as_view(),name="update_delivery"),
]