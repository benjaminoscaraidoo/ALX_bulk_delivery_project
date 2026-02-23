from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.views import View
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.views import APIView
from rest_framework import status
from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from .forms import UpdateUserForm, ChangePasswordForm, CustomerProfileForm, DriverProfileForm
from django.http import JsonResponse
import jwt
from django.conf import settings
from django.contrib import messages

from .serializers import (DriverApprovalSerializer,CustomerProfileSerializer,DriverProfileSerializer,MyTokenObtainPairSerializer,RegisterSerializer )
from customer.models import CustomUser, CustomerProfile, DriverProfile

# Create your views here.

UserR = get_user_model()

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

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
    
    
    if request.user.role == request.user.Role.CUSTOMER:
        return render(request, "customer/home.html")
    elif request.user.role == request.user.Role.DRIVER:
        return render(request, "driver/home.html")
    
@login_required
def driver_home(request):
    """Driver Home"""
    if request.user.role != request.user.Role.DRIVER:
        messages.error(request, "You are not authorized to view this page.")
        return redirect("customer:login")
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
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")
        role = request.POST.get("role", "customer")

        password = password2

        if password1 != password2:
            messages.error(request, "Passwords do not match")
            return redirect("customer:register")


        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "Email already exists")
            return redirect("customer:register")

        user = CustomUser.objects.create_user(
            email=email,
            phone_number=phone,
            password=password2,
            role=role,
        )

        login(request, user)
        return redirect("customer:update_profile")

    return render(request, "auth/register.html")

class RegisterAPIView(APIView):
    permission_classes = [AllowAny]  # Allow public access

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "message": "User registered successfully",
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "phone": user.phone_number,
                        "role": user.role,
                    },
                    "tokens": {
                        "access": str(refresh.access_token),
                        "refresh": str(refresh),
                    },
                },
                status=status.HTTP_201_CREATED,

            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
    
class RoleBasedProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role == "customer":
            profile, _ = CustomerProfile.objects.get_or_create(user=user)
            serializer = CustomerProfileSerializer(profile)
            return Response(serializer.data)

        elif user.role == "driver":
            profile, _ = DriverProfile.objects.get_or_create(user=user)
            serializer = DriverProfileSerializer(profile)
            return Response(serializer.data)

        return Response(
            {"error": "Invalid user role."},
            status=status.HTTP_400_BAD_REQUEST
        )

    def put(self, request):
        user = request.user

        if user.role == "customer":
            profile, _ = CustomerProfile.objects.get_or_create(user=user)
            serializer = CustomerProfileSerializer(
                profile,
                data=request.data,
                partial=True
            )

        elif user.role == "driver":
            profile, _ = DriverProfile.objects.get_or_create(user=user)
            serializer = DriverProfileSerializer(
                profile,
                data=request.data,
                partial=True
            )

        else:
            return Response(
                {"error": "Invalid user role."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if serializer.is_valid():
            profile = serializer.save()

            # Auto mark profile complete
            if user.role == "customer":
                if profile.customer_name and profile.address:
                    profile.is_complete = True
                    profile.save()

            if user.role == "driver":
                if (
                    profile.vehicle_type
                    and profile.vehicle_number
                    and profile.license_number
                ):
                    profile.is_complete = True
                    profile.save()

            return Response({
                "message": "Profile updated successfully",
                "profile": serializer.data
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DriverApprovalAPIView(APIView):
    permission_classes = [IsAdminUser]

    def put(self, request):
        try:
            email = request.data.get("email")
            action = request.data.get("action")

            if not email:
                return Response(
                    {"detail": "Email is required."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            user = get_object_or_404(UserR, email=email, role="driver")
            profile = get_object_or_404(DriverProfile, user=user)
        except DriverProfile.DoesNotExist:
            return Response(
                {"error": "Driver not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        if action == "approve":
            profile.approval_status = "approved"
            profile.is_approved = True
        elif action == "reject":
            profile.approval_status = "rejected"
        else:
            return Response(
                {"detail": "Invalid action. Use 'approve' or 'reject'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        profile.save()

        return Response(
            {"detail": f"Driver {profile.approval_status} successfully."},
            status=status.HTTP_200_OK
        )
    
    

def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)
        print("Authenticated user:", user)
        if user is not None:
            login(request, user)
            request.session.set_expiry(settings.AUTO_LOGOUT.get('IDLE_TIME', 1800)) #session logout timer 10secs
            print("User logged in:", request.user)
            # Redirect based on role
            if user.role == user.Role.CUSTOMER:
                return redirect("customer:home")  # customer home
            elif user.role == user.Role.DRIVER:
                return redirect("customer:driver_home")  # driver home
            elif user.role == user.Role.ADMIN:
                return redirect("/admin/")  # admin dashboard

        else:
            messages.error(request, "Invalid login credentials")
            return redirect("customer:login")

    return render(request, "auth/login.html")



def session_login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)
        if user:
            login(request, user)  # 🔥 CREATES DJANGO SESSION
            request.session.set_expiry(settings.AUTO_LOGOUT.get('IDLE_TIME', 1800)) #session logout timer 10secs
            return JsonResponse({"success": True})
        return JsonResponse({"success": False}, status=401)
    


def logout_view(request):
    logout(request)
    return redirect("customer:login")

def update_profile(request):
    user = request.user
    
    # Identify the profile and the specific form class needed
    if user.role == user.Role.CUSTOMER:
        profile, _ = CustomerProfile.objects.get_or_create(user=user)
        ProfileFormClass = CustomerProfileForm
        role_label = "Customer"
    elif user.role == user.Role.DRIVER:
        profile, _ = DriverProfile.objects.get_or_create(user=user)
        ProfileFormClass = DriverProfileForm
        role_label = "Driver"
    else:
        messages.info(request, "Admins do not have profiles to update.")
        return redirect("customer:home")

    if request.method == "POST":
        user_form = UpdateUserForm(request.POST, instance=user)
        profile_form = ProfileFormClass(request.POST, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect("customer:home")
    else:
        user_form = UpdateUserForm(instance=user)
        profile_form = ProfileFormClass(instance=profile)

    return render(request, "customer/update_profile.html", {
        "user_form": user_form,
        "profile_form": profile_form,
        "role_label": role_label
    })



def update_password(request):
	if request.user.is_authenticated:
		current_user = request.user
		# Did they fill out the form
		if request.method  == 'POST':
			form = ChangePasswordForm(current_user, request.POST)
			# Is the form valid
			if form.is_valid():
				form.save()
				messages.success(request, "Your Password Has Been Updated...")
				login(request, current_user)
				return redirect('update_user')
			else:
				for error in list(form.errors.values()):
					messages.error(request, error)
					return redirect('update_password')
		else:
			form = ChangePasswordForm(current_user)
			return render(request, "customer/update_password.html", {'form':form})
	else:
		messages.success(request, "You Must Be Logged In To View That Page...")
		return redirect('home')
     

def update_user(request):
	if request.user.is_authenticated:
		current_user = UserR.objects.get(id=request.user.id)
		user_form = UpdateUserForm(request.POST or None, instance=current_user)

		if user_form.is_valid():
			user_form.save()

			login(request, current_user)
			messages.success(request, "User Has Been Updated!!")
			return redirect('home')
		return render(request, "customer/update_user.html", {'user_form':user_form})
	else:
		messages.success(request, "You Must Be Logged In To Access That Page!!")
		return redirect('home')
    
