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

from .serializers import (DriverApprovalSerializer,CustomerProfileSerializer,DriverProfileSerializer,MyTokenObtainPairSerializer,RegisterSerializer,RegisterSuperUserSerializer)
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
    


class RegisterSuperUserAPIView(APIView):
    permission_classes = [AllowAny]  # Allow public access

    def post(self, request):
        serializer = RegisterSuperUserSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "message": "Super User registered successfully",
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
     


