from .views import CreateDeliveriesAPIView,DriverDeliveryUpdateAPIView,DeliveryListAPIView
from django.urls import path
from .payment_views import PaymentCreateAPIView, PaymentListAPIView, PaymentConfirmAPIView

app_name = "delivery"

urlpatterns = [
    path("v1/payment/create/", PaymentCreateAPIView.as_view()),
    path("v1/search/payment/", PaymentListAPIView.as_view()),
    path("v1/payment/<str:pk>/confirm/", PaymentConfirmAPIView.as_view()),
    path("v1/search/delivery/", DeliveryListAPIView.as_view(), name="search_delivery"),
    path("v1/delivery/create/",CreateDeliveriesAPIView.as_view(),name="create_deliveries"),
    path("v1/delivery/update/",DriverDeliveryUpdateAPIView.as_view(),name="update_delivery"),
]