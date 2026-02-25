from django.shortcuts import render, get_object_or_404, redirect
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from django.contrib.auth.decorators import login_required
from rest_framework.response import Response
from django.db import transaction
from django.contrib import messages
from rest_framework.views import APIView
from rest_framework.generics import UpdateAPIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from customer.permissions import (
    IsDriver,
    IsAssignedDriverOrAdmin,
    IsDriverProfileComplete
)
from .models import Delivery,Payment
from order.models import Order,Package
from .serializers import DeliverySerializer,PaymentSerializer,CreateDeliveriesSerializer,DriverDeliveryUpdateSerializer

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
    
    
#@login_required
def add_deliveries(request, order_id):


    user = request.user

    if not user.is_authenticated:
        return render(request, 'home.html')
    

    order = get_object_or_404(Order, id=order_id, customer_id=request.user)
    

    if request.method == "POST":
        description = request.POST.getlist("description")
        dimensions = request.POST.getlist("dimensions")
        receiver_names = request.POST.getlist("receiver_name")
        phones = request.POST.getlist("receiver_phone")
        addresses = request.POST.getlist("delivery_address")
        notes = request.POST.getlist("delivery_notes")
        fragile_flags = request.POST.getlist("is_fragile")
        value = request.POST.getlist("value")

        if not description:
            messages.error(request, "At least one package is required.")
            return redirect("delivery:add_deliveries", order_id=order.id)

        with transaction.atomic():
            for i in range(len(description)):
                new_package = Package.objects.create(
                    order_id=order,
                    description=description[i],
                    dimensions = dimensions[i],
                    receiver_name=receiver_names[i],
                    receiver_phone=phones[i],
                    fragile=(str(i) in fragile_flags),
                    value = value[i]
                )

                Delivery.objects.create(
                    package_id=new_package,
                    address=addresses[i],
                    delivery_notes=notes[i]
                )


            return redirect("order:order_detail", order_id=order.id)

    return render(request, "delivery/add_deliveries.html", {
        "order": order
    })




class CreateDeliveriesAPIView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = CreateDeliveriesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                deliveries = serializer.save()

        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                "detail": f"{len(deliveries)} deliveries created successfully.",
                "delivery_ids": [d.id for d in deliveries]
            },
            status=status.HTTP_201_CREATED
        )
    


class DriverDeliveryUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsDriverProfileComplete]

    def put(self, request):
        serializer = DriverDeliveryUpdateSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            delivery = serializer.save()
            return Response(
                {   
                    "id": delivery.id, 
                    "Delivery Status":delivery.delivery_status
                },
                status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    



class DriverDeliveryUpdateAPIView1(UpdateAPIView):
    serializer_class = DriverDeliveryUpdateSerializer
    permission_classes = [IsAuthenticated, IsDriverProfileComplete]

    def get_queryset(self):
        return Delivery.objects.filter(
            rider__user=self.request.user
        )
    