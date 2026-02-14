from django.shortcuts import render, get_object_or_404, redirect
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from django.contrib.auth.decorators import login_required
from rest_framework.response import Response
from django.utils import timezone
from customer.permissions import (
    IsDriver,
    IsAssignedDriverOrAdmin
)
from .models import Delivery,Payment
from order.models import Order
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
    
    
@login_required
def add_deliveries(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if request.method == "POST":
        package_names = request.POST.getlist("package_name")
        receiver_names = request.POST.getlist("receiver_name")
        phones = request.POST.getlist("receiver_phone")
        addresses = request.POST.getlist("delivery_address")
        notes = request.POST.getlist("delivery_notes")

        for i in range(len(package_names)):
            Delivery.objects.create(
                order=order,
                package_name=package_names[i],
                receiver_name=receiver_names[i],
                receiver_phone=phones[i],
                delivery_address=addresses[i],
                delivery_notes=notes[i],
            )

        return redirect("order:order_detail", order_id=order.id)

    return render(request, "delivery/add_deliveries.html", {
        "order": order
    })
