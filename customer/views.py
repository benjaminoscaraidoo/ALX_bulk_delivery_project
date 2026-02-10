from django.shortcuts import render, redirect
from rest_framework import viewsets, permissions
from .models import CustomerProfile, DriverProfile
from django.contrib.auth import authenticate, login,logout
from django.contrib.auth.decorators import login_required
from django.views import View
from django.contrib import messages
from .serializers import (CustomerProfileSerializer,DriverProfileSerializer)
from customer.models import CustomUser
# Create your views here.

class CustomerProfileViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CustomerProfile.objects.filter(user=self.request.user)


class DriverProfileViewSet(viewsets.ModelViewSet):
    serializer_class = DriverProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DriverProfile.objects.filter(user=self.request.user)
    
#@login_required
def home(request):
    user = request.user

    if not user.is_authenticated:
        return render(request, 'home.html')
    
    if user.role == "customer":
        return render(request, "customer/home.html")
    elif user.role == "driver":
        return render(request, "driver/home.html")
        

class Index(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'customer/index.html')
    
class About(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'customer/about.html')
    

def register_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        phone = request.POST.get("phone_number")
        password = request.POST.get("password")
        role = request.POST.get("role", "customer")

        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect("customer:register")

        user = CustomUser.objects.create_user(
            email=email,
            phone_number=phone,
            password=password,
            role=role,
        )

        login(request, user)
        return redirect("customer:update_profile")

    return render(request, "auth/register.html")

def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)

        if user is not None:
            login(request, user)
            return redirect("customer:home")

        messages.error(request, "Invalid login credentials")
        return redirect("core:login")

    return render(request, "auth/login.html")


def logout_view(request):
    logout(request)
    return redirect("customer:login")


@login_required
def update_profile(request):
    user = request.user

    if user.role == user.Role.CUSTOMER:
        profile = user.customer_profile
    elif user.role == user.Role.DRIVER:
        profile = user.driverprofile
    else:
        messages.error(request, "Admin does not have a profile to update.")
        return redirect("customer:home")

    if request.method == "POST":
        if user.role == user.Role.CUSTOMER:
            profile.customer_name = request.POST.get("customer_name")
            profile.address = request.POST.get("address")
        elif user.role == user.Role.DRIVER:
            profile.vehicle_type = request.POST.get("vehicle_type")
            profile.vehicle_number = request.POST.get("vehicle_number")
            profile.license_number = request.POST.get("license_number")
            profile.phone = request.POST.get("phone")
        profile.save()
        messages.success(request, "Successfully Profile updated !")
        return redirect("customer:home")

    return render(request, "customer/update_profile.html", {"profile": profile})