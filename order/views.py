from django.shortcuts import render
from rest_framework import viewsets, permissions
from .models import Order, Package
from .serializers import OrderSerializer, PackageSerializer
from rest_framework.permissions import IsAuthenticated
from customer.permissions import (
    IsCustomer,
    IsOrderOwnerOrAdmin,
    IsAdmin
)

# Create your views here.
class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [
        IsAuthenticated,
        IsCustomer | IsAdmin,
        IsOrderOwnerOrAdmin,
    ]

    def get_queryset(self):
        user = self.request.user
        if user.role == "admin":
            return Order.objects.all()
        return Order.objects.filter(customer=user)


class PackageViewSet(viewsets.ModelViewSet):
    serializer_class = PackageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Package.objects.filter(order__customer=self.request.user)

    def perform_create(self, serializer):
        order_id = self.kwargs.get("order_id")
        serializer.save(order_id=order_id)
