from rest_framework import viewsets, permissions,generics, filters as drf_filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Order, Package
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from .serializers import (
    OrderSerializer,
    PackageSerializer, 
    OrderCreateSerializer, 
    OrderAssignSerializer, 
    CreatePackagesSerializer,
    PackageDetailsUpdateSerializer,
    OrderCancelSerializer,
    OrderUpdateSerializer
)
from .filters import OrderFilter,PackageFilter
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from customer.permissions import (
    IsCustomer,
    IsOrderOwnerOrAdmin,
    IsAdmin,
    IsCustomerProfileComplete,
    IsDriverProfileComplete
)
from drf_spectacular.utils import (
    extend_schema,
    OpenApiExample,
    OpenApiResponse,
    OpenApiParameter
)


UserR = get_user_model()


# Create your views here.

# View for Orders
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


# View for Order creation
class OrderCreateAPIView(APIView):
    permission_classes = [IsAuthenticated,IsCustomerProfileComplete]

    @extend_schema(
        tags=["Orders"],
        summary="Create Order",
        description="Create a new Order by a customer.",
        request=CreatePackagesSerializer,
        responses={200: OpenApiResponse(description="Order created Successfully")},
        examples=[
            OpenApiExample(
                "Create Order Request",
                value={
                        "pickup_address": "Lapaz Accra"
                    },
                request_only=True,
            ),
            OpenApiExample(
                "Create Order Response",
                value={
                        "id": "ORDBD5...",
                        "Pickup_address": "Lapaz Accra",
                        "order_status": "pending"                      
                },
                response_only=True,
            ),
        ],
    )

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            order = serializer.save()
            return Response(
                {   
                    "id": order.id, 
                    "Pickup_address":order.pickup_address,
                    "order_status": order.order_status
                },
                status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    


# View for Assigning order to a driver/rider
class OrderAssignAPIView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        tags=["Admin"],
        summary="Assign Driver to Order",
        description="Assign a driver to deliver packages for an Order.",
        request=CreatePackagesSerializer,
        responses={200: OpenApiResponse(description="Order Assigned to Driver Successfully")},
        examples=[
            OpenApiExample(
                "Assign Driver to Order Request",
                value={
                        "order_id":"ORD383...",
                        "driver_email":"asango@gmail.com" 
                    },
                request_only=True,
            ),
            OpenApiExample(
                "Assign Driver To Order Response",
                value={
                    "detail": "Order ORDB... Driver assigned successfully"                        
                },
                response_only=True,
            ),
        ],
    )

    def put(self, request):
        try:
            order_id = request.data.get("order_id")
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = OrderAssignSerializer(data=request.data, context={"order": order})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({"detail": f" Order {order.id} Driver assigned successfully."}, status=status.HTTP_200_OK)
    

# View for cancelling orders
class OrderCancelAPIView(APIView):
    permission_classes = [IsAuthenticated,IsCustomerProfileComplete]

    @extend_schema(
        tags=["Orders"],
        summary="Cancel Order",
        description="Cancel a created Order.",
        request=CreatePackagesSerializer,
        responses={200: OpenApiResponse(description="Order cancelled Successfully")},
        examples=[
            OpenApiExample(
                "Cancel Order Request",
                value={
                    "order_id" :"ORDB...",
                    "cancel_reason":"Mistaken Order"
                    },
                request_only=True,
            ),
            OpenApiExample(
                "Create Package Response",
                value={
                    "id": "ORDB...", 
                    "Order Status":"cancelled"
                        
                },
                response_only=True,
            ),
        ],
    )

    def put(self, request):
        serializer = OrderCancelSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            order = serializer.save()
            return Response(
                {   
                    "id": order.id, 
                    "Order Status":order.order_status
                },
                status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

@extend_schema(
    tags=["Orders"],
    summary="Search Orders",
    description="Returns Orders depending on the logged-in user's role."
)
# View for order filtering search
class OrderListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]

    
    serializer_class = OrderSerializer

    filter_backends = [
        DjangoFilterBackend, 
        drf_filters.SearchFilter, 
        drf_filters.OrderingFilter
    ]
    

    filterset_class = OrderFilter

    search_fields = ['id', 'pickup_address', 'cancel_reason']

    def get_queryset(self):

        user = self.request.user
        
        if user.is_staff:
            return Order.objects.all()
            
        return Order.objects.filter(customer_id=user)


    ordering_fields = ['created_at', 'total_price']
    ordering = ['-created_at']


# View for creating packages for orders
class CreatePackagesAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCustomerProfileComplete]

    @extend_schema(
        tags=["Packages"],
        summary="Create Packages",
        description="Create new packages for Orders.",
        request=CreatePackagesSerializer,
        responses={200: OpenApiResponse(description="Packages created Successfully")},
        examples=[
            OpenApiExample(
                "Create Package Request",
                value={
                    "order_id" :"ORDB...",
                        "packages": [
                            {
                                "description" : "phone",
                                "dimensions" : "Big" ,
                                "value" : "6000",
                                "fragile" : "False",
                                "receiver_name" : "Akua mansa",
                                "receiver_phone" : "+2332434..."
                            },
                            {
                                "description" : "Food",
                                "dimensions" : "Small" ,
                                "value" : "250",
                                "fragile" : "True",
                                "receiver_name" : "Mark Stone",
                                "receiver_phone" : "+2332432..."
                            }
                        ]
                    },
                request_only=True,
            ),
            OpenApiExample(
                "Create Package Response",
                value={
                        "detail": "2 packages created successfully.",
                        "package_ids": [
                                "PKGF7...",
                                "PKGE6..."
                        ]
                },
                response_only=True,
            ),
        ],
    )

    def post(self, request):
        serializer = CreatePackagesSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        packages = serializer.save()

        return Response(
            {
                "detail": f"{len(packages)} packages created successfully.",
                "package_ids": [pkg.id for pkg in packages]
            },
            status=status.HTTP_201_CREATED
        )
    

# View for updating packages information(receiver details) for orders
class PackageDetailsUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCustomerProfileComplete]

    @extend_schema(
        tags=["Packages"],
        summary="Updage Package Details",
        description="Update Receiver Details for a package.",
        request=CreatePackagesSerializer,
        responses={200: OpenApiResponse(description="Packages updated Successfully")},
        examples=[
            OpenApiExample(
                "Update Package Request",
                value={
                        "package_id": "PKGBC...",
                        "receiver_name" : "Akua mansa",
                        "receiver_phone" : "+2332768..."
                },
                request_only=True,
            ),
            OpenApiExample(
                "Update Package Response",
                value={
                    "id":  "PKGBC...",
                    "Receiver Name":"Akua mansa",
                    "Receiver Phone":"+2332768..."
                },
                response_only=True,
            ),
        ],
    )

    def put(self, request):
        serializer = PackageDetailsUpdateSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            package = serializer.save()
            return Response(
                {   
                    "id": package.id, 
                    "Receiver Name":package.receiver_name,
                    "Receiver Phone":package.receiver_phone,
                },
                status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

@extend_schema(
    tags=["Packages"],
    summary="Search Packages",
    description="Returns Packages depending on the logged-in user's role."
)
class PackageListAPIView(generics.ListAPIView):

    serializer_class = PackageSerializer
    permission_classes = [IsAuthenticated]

    filter_backends = [
        DjangoFilterBackend,
        drf_filters.SearchFilter,
        drf_filters.OrderingFilter,
    ]

    filterset_class = PackageFilter

    search_fields = [
        "id",
        "description",
        "receiver_name",
        "receiver_phone",
    ]


    def get_queryset(self):
        user = self.request.user

        if user.role == "admin":
            return Package.objects.all()

        if user.role == "driver":
            return Package.objects.filter(
                order_id__deliveries__rider=user
            )

        # customer
        return Package.objects.filter(
            order_id__customer_id=user
        )
    
    ordering_fields = [
        "value",
    ]

    ordering = ["-value"]



class OrderPickupUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsDriverProfileComplete]

    @extend_schema(
        tags=["Orders"],
        summary="Order Pickup Update",
        description="Update pickeup status by Driver.",
        request=CreatePackagesSerializer,
        responses={200: OpenApiResponse(description="Order status updated Successfully")},
        examples=[
            OpenApiExample(
                "Order Pickup Status Request",
                value={
                        "status":"picked_up",
                        "order_id":"ORDBD5..."
                    },
                request_only=True,
            ),
            OpenApiExample(
                "Order Pickup Status Response",
                value={
                    "message": "All deliveries updated to picked_up successfully.",
                    "order_id": "ORDBD5...",
                    "order_status": "picked_up"    
                },
                response_only=True,
            ),
        ],
    )

    def put(self, request):
        serializer = OrderUpdateSerializer(
            data=request.data,
            context={"request": request}
        )

        if serializer.is_valid():
            order = serializer.save()

            return Response(
                {
                    "message": "All deliveries updated to picked_up successfully.",
                    "order_id": order.id,
                    "order_status": order.order_status,
                },
                status=status.HTTP_200_OK
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )