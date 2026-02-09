from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from customer.permissions import (
    IsDriver,
    IsAssignedDriverOrAdmin
)
from .models import Delivery,Payment
from .serializers import DeliverySerializer,PaymentSerializer

# Create your views here.
class DeliveryViewSet(viewsets.ModelViewSet):
    serializer_class = DeliverySerializer
    permission_classes = [
        permissions.IsAuthenticated,
        IsAssignedDriverOrAdmin,
    ]

    def get_queryset(self):
        user = self.request.user
        if user.role == "driver":
            return Delivery.objects.filter(driver=user)
        if user.role == "admin":
            return Delivery.objects.all()
        return Delivery.objects.filter(order__customer=user)

    @action(detail=True, methods=["put"])
    def pickup(self, request, pk=None):
        delivery = self.get_object()
        delivery.delivery_status = "picked_up"
        delivery.picked_up_at = timezone.now()
        delivery.save()
        return Response({"status": "picked up"})

    @action(detail=True, methods=["put"])
    def deliver(self, request, pk=None):
        delivery = self.get_object()
        delivery.delivery_status = "delivered"
        delivery.delivered_at = timezone.now()
        delivery.save()
        return Response({"status": "delivered"})


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "admin":
            return Payment.objects.all()
        return Payment.objects.filter(order__customer=user)