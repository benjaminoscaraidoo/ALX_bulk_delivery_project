from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.views import APIView
from rest_framework import status
from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken,AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView
from .services import send_otp
from rest_framework_simplejwt.exceptions import TokenError
from .throttles import OTPVerifyThrottle, OTPRegisterThrottle
from django.conf import settings

from .serializers import (
    DriverApprovalSerializer,
    CustomerProfileSerializer,
    DriverProfileSerializer,
    MyTokenObtainPairSerializer,
    RegisterSerializer,
    RegisterSuperUserSerializer,
    ResetPasswordSerializer,
    VerifyOTPSerializer,
    PasswordResetRequestSerializer,
    PasswordResetVerifySerializer,
    PasswordResetConfirmSerializer)
from customer.models import CustomUser, CustomerProfile, DriverProfile, EmailOTP

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
    throttle_classes = [OTPRegisterThrottle]

    permission_classes = [AllowAny]  # Allow public access

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            send_otp(user)

            return Response({
                "message": "OTP sent to your email"
            }, status=status.HTTP_201_CREATED)
        

            # Generate JWT tokens
           # refresh = RefreshToken.for_user(user)

          #  return Response(
           #     {
             #       "message": "User registered successfully",
           #         "user": {
             #           "id": user.id,
            #            "email": user.email,
            #            "phone": user.phone_number,
           #             "role": user.role,
           #         },
           #         "tokens": {
           #             "access": str(refresh.access_token),
          ##              "refresh": str(refresh),
          #          },
          #      },
             #   status=status.HTTP_201_CREATED,

            #)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class RegisterSuperUserAPIView(APIView):
    throttle_classes = [OTPRegisterThrottle]
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
    


class ResetPasswordAPIView(APIView):
    permission_classes = [AllowAny]  # Allow public access

    def put(self, request):
        serializer = ResetPasswordSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            return Response(
                {
                    "message": "Password Reset successfully",
                    "user": {
                        "id": user.id,
                    },
                },
                status=status.HTTP_201_CREATED,

            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyOTPAPIView(APIView):
    throttle_classes = [OTPVerifyThrottle]

    def post(self, request):

        serializer = VerifyOTPSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        email = serializer.validated_data["email"]
        otp_entered = serializer.validated_data["otp"]

        try:
            user = UserR.objects.get(email=email)
        except UserR.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        otp_obj = EmailOTP.objects.filter(
            user=user,
            is_verified=False
        ).last()

        if not otp_obj:
            return Response({"error": "No active OTP"}, status=400)

        # 🔒 Check lock
        if otp_obj.is_locked():
            return Response(
                {"error": "Too many failed attempts. OTP locked."},
                status=403
            )

        # ⏳ Check expiry
        if otp_obj.is_expired():
            return Response(
                {"error": "OTP expired"},
                status=400
            )

        # ❌ Wrong OTP
        if otp_obj.otp != otp_entered:
            otp_obj.attempt_count += 1
            otp_obj.save()

            return Response(
                {"error": f"Invalid OTP. Attempts left: {otp_obj.max_attempts - otp_obj.attempt_count}"},
                status=400
            )

        # ✅ Success
        user.is_active = True
        user.save()

        otp_obj.is_verified = True
        otp_obj.save()

        refresh = RefreshToken.for_user(user)

        return Response({
            "message": "Email verified",
            "refresh": str(refresh),
            "access": str(refresh.access_token)
        })
    


class PasswordResetRequestAPIView(APIView):
    throttle_classes = [OTPRegisterThrottle]  # reuse throttle

    def post(self, request):

        serializer = PasswordResetRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        email = serializer.validated_data["email"]

        try:
            user = UserR.objects.get(email=email)
        except UserR.DoesNotExist:
            # Do NOT reveal if email exists
            return Response({"message": "If account exists, OTP sent"})

        # Delete old reset OTPs
        EmailOTP.objects.filter(user=user, otp_purpose="password_reset").delete()

        send_otp(user, otp_purpose="password_reset")

        return Response({"message": "If account exists, OTP sent"})
    

class PasswordResetVerifyAPIView(APIView):
    throttle_classes = [OTPVerifyThrottle]

    def post(self, request):

        serializer = PasswordResetVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        email = serializer.validated_data["email"]
        otp_entered = serializer.validated_data["otp"]

        try:
            user = UserR.objects.get(email=email)
        except UserR.DoesNotExist:
            return Response({"error": "Invalid request"}, status=400)

        otp_obj = EmailOTP.objects.filter(
            user=user,
            otp_purpose="password_reset",
            is_verified=False
        ).last()

        if not otp_obj:
            return Response({"error": "Invalid OTP"}, status=400)

        if otp_obj.is_locked():
            return Response({"error": "Too many attempts"}, status=403)

        if otp_obj.is_expired():
            return Response({"error": "OTP expired"}, status=400)

        if otp_obj.otp != otp_entered:
            otp_obj.attempt_count += 1
            otp_obj.save()
            return Response({"error": "Invalid OTP"}, status=400)

        # Mark OTP verified
        otp_obj.is_verified = True
        otp_obj.save()

        # Issue short-lived reset token (5 minutes)
        token = AccessToken.for_user(user)
        token["scope"] = "password_reset"

        return Response({
            "reset_token": str(token)
        })
    

class PasswordResetConfirmAPIView(APIView):

    def post(self, request):

        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        token = serializer.validated_data["reset_token"]
        new_password = serializer.validated_data["new_password"]

        try:
            access = AccessToken(token)
        except TokenError:
            return Response({"error": "Invalid token"}, status=400)

        if access.get("scope") != "password_reset":
            return Response({"error": "Invalid scope"}, status=403)

        user_id = access["user_id"]
        user = UserR.objects.get(id=user_id)

        user.set_password(new_password)
        user.save()

        return Response({"message": "Password reset successful"})