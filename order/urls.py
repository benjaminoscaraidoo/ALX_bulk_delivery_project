from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, PackageViewSet, create_order,order_detail,OrderCreateAPIView,OrderAssignAPIView, CreatePackagesAPIView
from django.urls import path, include

app_name = "order"


urlpatterns = [
    #path("create/", create_order, name="create_order"),
    #path("<int:order_id>/", order_detail, name="order_detail"),
    path("api/v1/create/", OrderCreateAPIView.as_view(), name="create_order"),
    path("api/v1/order_assign/", OrderAssignAPIView.as_view(), name="assign_order"),
    path("api/v1/packages/create/",CreatePackagesAPIView.as_view(),name="create_packages"),
]