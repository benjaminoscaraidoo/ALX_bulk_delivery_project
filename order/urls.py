from .views import (
    OrderCreateAPIView,
    OrderAssignAPIView,
    CreatePackagesAPIView,
    PackageDetailsUpdateAPIView,
    OrderCancelAPIView
    )
from django.urls import path

app_name = "order"


urlpatterns = [
    path("api/v1/create/", OrderCreateAPIView.as_view(), name="create_order"),
    path("api/v1/order/assign/", OrderAssignAPIView.as_view(), name="assign_order"),
    path("api/v1/order/cancel/", OrderCancelAPIView.as_view(), name="cancel_order"),
    path("api/v1/package/create/",CreatePackagesAPIView.as_view(),name="create_packages"),
    path("api/v1/package/update/",PackageDetailsUpdateAPIView.as_view(),name="update_packages"),
]