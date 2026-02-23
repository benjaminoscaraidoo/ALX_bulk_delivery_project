from django.shortcuts import render, redirect, get_object_or_404
from rest_framework import viewsets, permissions
from .models import Order, Package
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from customer.models import DriverProfile
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from .serializers import OrderSerializer, PackageSerializer, OrderCreateSerializer, OrderAssignSerializer, CreatePackagesSerializer
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from customer.permissions import (
    IsCustomer,
    IsOrderOwnerOrAdmin,
    IsAdmin,
    IsCustomerProfileComplete
)


UserR = get_user_model()


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
    


#@login_required
def create_order(request):
    user = request.user

    if not user.is_authenticated:
        return render(request, 'home.html')

    if request.method == "POST":
        #total_amount = request.POST.get("total_amount")
        pickup_address = request.POST.get("pickup_address")

        order = Order.objects.create(
            customer_id=request.user,
            #total_amount=total_amount,
            pickup_address = pickup_address,
            order_status="Pending"
        )

        # Redirect to delivery step
        return redirect("delivery:add_deliveries", order_id=order.id)

    return render(request, "order/create_order.html")


def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    return render(request, "order/order_detail.html", {"order": order})

     #test_display=get_object_or_404(Order.objects.prefetch_related('order'), id)  
     # or Model1.objects.prefetch_related('model_one').get(pk=pk)
     #return render(request, 'order/order_detail.html', {'test_display':test_display})


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