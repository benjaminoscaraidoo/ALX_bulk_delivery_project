from .views import (
    OrderCreateAPIView,
    OrderAssignAPIView,
    CreatePackagesAPIView,
    PackageDetailsUpdateAPIView,
    OrderCancelAPIView,
    OrderListAPIView,
    PackageListAPIView,
    OrderPickupUpdateAPIView
    )
from django.urls import path

app_name = "order"


urlpatterns = [
    path("v1/order/create/", OrderCreateAPIView.as_view(), name="create_order"),
    path("v1/search/order/", OrderListAPIView.as_view(), name="search_order"),
    path("v1/search/package/", PackageListAPIView.as_view(), name="search_package"),
    path("v1/order/assign/", OrderAssignAPIView.as_view(), name="assign_order"),
    path("v1/order/update/", OrderPickupUpdateAPIView.as_view(), name="update_order"),
    path("v1/order/cancel/", OrderCancelAPIView.as_view(), name="cancel_order"),
    path("v1/package/create/",CreatePackagesAPIView.as_view(),name="create_packages"),
    path("v1/package/update/",PackageDetailsUpdateAPIView.as_view(),name="update_packages"),
]