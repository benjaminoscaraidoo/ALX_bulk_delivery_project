from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, PackageViewSet, create_order
from django.urls import path, include

app_name = "order"

urlpatterns = [
    path("create/", create_order, name="create_order"),
]