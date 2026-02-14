from rest_framework.routers import DefaultRouter
from .views import add_deliveries
from django.urls import path, include

app_name = "delivery"

urlpatterns = [
    path("add/<int:order_id>/", add_deliveries, name="add_deliveries"),
]