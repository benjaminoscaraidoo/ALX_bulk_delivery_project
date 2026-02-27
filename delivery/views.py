from django.shortcuts import render, get_object_or_404, redirect
from rest_framework import viewsets, permissions, status
from rest_framework import viewsets, permissions,generics, filters as drf_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from django.contrib.auth.decorators import login_required
from rest_framework.response import Response
from django.db import transaction
from django.contrib import messages
from rest_framework.views import APIView
from rest_framework.generics import UpdateAPIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from .filters import DeliveryFilter
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
            return Delivery.objects.filter(rider=user)
        if user.role == "admin":
            return Delivery.objects.all()
        #return Delivery.objects.filter(order__customer=user)
        return Delivery.objects.filter(package_id__order_id__customer_id=user)

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
    


class DeliveryListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAssignedDriverOrAdmin]

    
    serializer_class = DeliverySerializer
    
    # Combined backends: DjangoFilter (for dates/status) + SearchFilter (for text)
    filter_backends = [
        DjangoFilterBackend, 
        drf_filters.SearchFilter, 
        drf_filters.OrderingFilter
    ]
    
    # Link the custom date filter class
    filterset_class = DeliveryFilter
    
    # Text search fields (accessed via ?search=...)
    search_fields = ['id', 'address', 'delivery_notes']

    def get_queryset(self):

        user = self.request.user

        if user.role == "driver":
            return Delivery.objects.filter(rider=user)
        if user.role == "admin":
            return Delivery.objects.all()
        return Delivery.objects.filter(package_id__order_id__customer_id=user)


    # Default ordering
    ordering_fields = ['picked_up_at', 'delivered_at', 'assigned_at']
    ordering = ['-assigned_at']
