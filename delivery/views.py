from rest_framework import viewsets, permissions, status
from rest_framework import viewsets, permissions,generics, filters as drf_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.utils import timezone
from .filters import DeliveryFilter
from customer.permissions import (
    IsDriver,
    IsAssignedDriverOrAdmin,
    IsDriverProfileComplete,
    IsCustomerProfileComplete
)
from .models import Delivery,Payment
from .serializers import DeliverySerializer,PaymentSerializer,CreateDeliveriesSerializer,DriverDeliveryUpdateSerializer
from drf_spectacular.utils import (
    extend_schema,
    OpenApiExample,
    OpenApiResponse,
    OpenApiParameter
)

# Create your views here.

# View for Delivery 
class DeliveryViewSet(viewsets.ModelViewSet):
    serializer_class = DeliverySerializer
    permission_classes = [
        permissions.IsAuthenticated,
        IsAssignedDriverOrAdmin,
    ]
    @extend_schema(
        tags=["Delivery"],
        summary="List Deliveries",
        description="Retrieve deliveries depending on user role (driver, admin, or customer).",
        responses={200: DeliverySerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        tags=["Delivery"],
        summary="Retrieve Delivery",
        description="Get details of a specific delivery.",
        responses={200: DeliverySerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        if user.role == "driver":
            return Delivery.objects.filter(rider=user)
        if user.role == "admin":
            return Delivery.objects.all()
        #return Delivery.objects.filter(order__customer=user)
        return Delivery.objects.filter(package_id__order_id__customer_id=user)

    @extend_schema(
        tags=["Delivery"],
        summary="Pickup Delivery",
        description="Driver marks a delivery as picked up.",
        responses={200: OpenApiResponse(description="Delivery picked up")},
    )
    @action(detail=True, methods=["put"])
    def pickup(self, request, pk=None):
        delivery = self.get_object()
        delivery.delivery_status = "picked_up"
        delivery.picked_up_at = timezone.now()
        delivery.save()
        return Response({"status": "picked up"})


    @extend_schema(
        tags=["Delivery"],
        summary="Complete Delivery",
        description="Driver marks a delivery as delivered.",
        responses={200: OpenApiResponse(description="Delivery delivered")},
    )
    @action(detail=True, methods=["put"])
    def deliver(self, request, pk=None):
        delivery = self.get_object()
        delivery.delivery_status = "delivered"
        delivery.delivered_at = timezone.now()
        delivery.save()
        return Response({"status": "delivered"})


# View for Payment
class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "admin":
            return Payment.objects.all()
        return Payment.objects.filter(order__customer=user)
    


#View for Creating Deliveries
class CreateDeliveriesAPIView(APIView):
    permission_classes = [IsCustomerProfileComplete]

    @extend_schema(
        tags=["Delivery"],
        summary="Create Delivery",
        description="Create new deliveries for customers.",
        request=CreateDeliveriesSerializer,
        responses={200: OpenApiResponse(description="Deliveries Created Successfully")},
        examples=[
            OpenApiExample(
                "Create Deliveries Request",
                value={
                        "deliveries": [
                                {
                                    "package_id":"PKGE68...",
                                    "address" : "Accra Mall Gate 2"

                                },
                                {
                                    "package_id":"PKGF79...",
                                    "address" : "Sakaman junction"
                                }
                    ]
                },
                request_only=True,
            ),
            OpenApiExample(
                "Create Deliveries Response",
                value={
                        "detail": "2 deliveries created successfully.",
                            "delivery_ids": [
                                    "DEL4D7...",
                                    "DEL5A7..."
                        ]
                },
                response_only=True,
            ),
        ],
    )

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
    


# View for Delivery update by driver/rider
class DriverDeliveryUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsDriverProfileComplete]

    @extend_schema(
        tags=["Delivery"],
        summary="Driver Update Delivery",
        description="Delivery status update by drivers.",
        request=DriverDeliveryUpdateSerializer,
        responses={200: OpenApiResponse(description="Delivery Status Updated Successfully")},
        examples=[
            OpenApiExample(
                "Update Delivery Status Request",
                value={
                        "package_id":"PKGE68...",
                        "delivery_status" : "picked_up"
                },
                request_only=True,
            ),
            OpenApiExample(
                "Update Delivery Status Response",
                value={

                        "Delivery_id":"DEL982...",
                        "delivery_status" : "picked_up" 
                },
                response_only=True,
            ),
        ],
    )

    def put(self, request):
        serializer = DriverDeliveryUpdateSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            delivery = serializer.save()
            return Response(
                {   
                    "Delivery_id": delivery.id, 
                    "Delivery Status":delivery.delivery_status
                },
                status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    


# View for Delivery List Filter

@extend_schema(
    tags=["Delivery"],
    summary="Search deliveries",
    description="Returns deliveries depending on the logged-in user's role."
)
class DeliveryListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAssignedDriverOrAdmin]

    
    serializer_class = DeliverySerializer
    
    filter_backends = [
        DjangoFilterBackend, 
        drf_filters.SearchFilter, 
        drf_filters.OrderingFilter
    ]
    
    filterset_class = DeliveryFilter
    
    search_fields = [
        'id', 
        'address', 
        'delivery_notes'
        ]

    def get_queryset(self):

        user = self.request.user

        if user.role == "driver":
            return Delivery.objects.filter(rider=user)
        if user.role == "admin":
            return Delivery.objects.all()
        return Delivery.objects.filter(package_id__order_id__customer_id=user)

    ordering_fields = ['picked_up_at', 'delivered_at', 'assigned_at']
    ordering = ['-assigned_at']
