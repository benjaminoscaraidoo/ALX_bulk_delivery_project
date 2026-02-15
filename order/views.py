from django.shortcuts import render, redirect, get_object_or_404
from rest_framework import viewsets, permissions
from .models import Order, Package
from django.contrib.auth.decorators import login_required
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