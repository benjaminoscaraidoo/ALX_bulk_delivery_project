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
    OrderCancelSerializer
)
from .filters import OrderFilter
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from customer.permissions import (
    IsCustomer,
    IsOrderOwnerOrAdmin,
    IsAdmin,
    IsCustomerProfileComplete
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