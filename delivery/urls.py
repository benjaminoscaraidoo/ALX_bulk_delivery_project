from .views import CreateDeliveriesAPIView,DriverDeliveryUpdateAPIView,DeliveryListAPIView
from django.urls import path

app_name = "delivery"

urlpatterns = [
    path("api/v1/delivery/", DeliveryListAPIView.as_view(), name="search_delivery"),
    path("api/v1/create/",CreateDeliveriesAPIView.as_view(),name="create_deliveries"),
    path("api/v1/updatedelivery/",DriverDeliveryUpdateAPIView.as_view(),name="update_delivery"),
]