from .views import CreateDeliveriesAPIView,DriverDeliveryUpdateAPIView,DeliveryListAPIView
from django.urls import path
from .payment_views import PaymentCreateAPIView, PaymentListAPIView, PaymentConfirmAPIView, PaymentReferenceAPIView

from .route_views import DriverRouteAPIView, DriverRouteOptimizeAPIView

from .lifecycle_views import DeliveryResolutionAPIView, DeliveryHistoryAPIView, DeliveryProofAPIView

app_name = "delivery"

urlpatterns = [
    path('v1/delivery/<str:pk>/resolution/', DeliveryResolutionAPIView.as_view()),
    path('v1/delivery/<str:pk>/history/', DeliveryHistoryAPIView.as_view()),
    path('v1/delivery/<str:pk>/proof/', DeliveryProofAPIView.as_view()),
    path("v1/driver/route/", DriverRouteAPIView.as_view()),
    path("v1/driver/route/optimize/", DriverRouteOptimizeAPIView.as_view()),
    path("v1/payment/<str:pk>/reference/", PaymentReferenceAPIView.as_view()),
    path("v1/payment/create/", PaymentCreateAPIView.as_view()),
    path("v1/search/payment/", PaymentListAPIView.as_view()),
    path("v1/payment/<str:pk>/confirm/", PaymentConfirmAPIView.as_view()),
    path("v1/search/delivery/", DeliveryListAPIView.as_view(), name="search_delivery"),
    path("v1/delivery/create/",CreateDeliveriesAPIView.as_view(),name="create_deliveries"),
    path("v1/delivery/update/",DriverDeliveryUpdateAPIView.as_view(),name="update_delivery"),
]