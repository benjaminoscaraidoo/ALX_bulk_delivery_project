from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.views import APIView
from rest_framework import status, serializers
from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken,AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenVerifyView, TokenRefreshView
from .services import send_otp, verify_otp, confirm_account_token
from rest_framework_simplejwt.exceptions import TokenError
from .throttles import OTPVerifyThrottle, OTPRegisterThrottle
from django.conf import settings

from .serializers import (
    DriverApprovalSerializer,
    CustomerProfileSerializer,
    DriverProfileSerializer,
    MyTokenObtainPairSerializer,
    RegisterRequestSerializer,
    RegisterVerifySerializer,
    RegisterConfirmSerializer,
    RegisterRequestSerializer,
    VerifyOTPSerializer,
    PasswordResetRequestSerializer,
    PasswordResetVerifySerializer,
    PasswordResetConfirmSerializer)
from customer.models import CustomUser, CustomerProfile, DriverProfile, EmailOTP
from drf_spectacular.utils import (
    extend_schema,
    OpenApiExample,
    OpenApiResponse,
    OpenApiParameter, inline_serializer, PolymorphicProxySerializer
)
from rest_framework_simplejwt.serializers import TokenVerifySerializer,TokenRefreshSerializer
# Create your views here.

UserR = get_user_model()



@extend_schema(
    tags=["System"],
    summary="API Root",
    description="Health check endpoint for Bulk Delivery API",
    responses={200: inline_serializer(name="HealthResponse", fields={"message": serializers.CharField(), "status": serializers.CharField()})},
)
@api_view(['GET'])
def api_root(request):
    return Response({"message": "Welcome to the Bulk Delivery API", "status": "success"})

# View to obtain token pair 
class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

    @extend_schema(
        tags=["Authentication"],
        summary="User Login",
        description="Authenticate user and return JWT access and refresh tokens.",
        request=MyTokenObtainPairSerializer,
        responses={200: OpenApiResponse(description="JWT tokens returned")},
        examples=[
            OpenApiExample(
                "Login Request",
                value={
                    "email": "user@gmail.com",
                    "password": "StrongPassword"
                },
                request_only=True,
            ),
            OpenApiExample(
                "Login Response",
                value={
                    "access": "eyJhbGc...",
                    "refresh": "eyJhbGc..."
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
    


class MyTokenVerifyView(TokenVerifyView):
    serializer_class = TokenVerifySerializer
    @extend_schema(
        tags=["Authentication"],
        summary="Token Verification",
        description="Verify generated JWT tokens.",
        request=TokenVerifySerializer,
        responses={200: OpenApiResponse(description="JWT tokens verified")},
        examples=[
            OpenApiExample(
                "Token Verification Request",
                value={
                    "token": "ak6ahags...",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Token Verification Response",
                value={
                    "message":"Token Verified"
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
    

class MyTokenRefreshView(TokenRefreshView):
    serializer_class = TokenRefreshSerializer
    @extend_schema(
        tags=["Authentication"],
        summary="Token Refresh",
        description="Refresh generated access JWT tokens.",
        request=TokenRefreshSerializer,
        responses={200: OpenApiResponse(description="JWT token Refresh")},
        examples=[
            OpenApiExample(
                "Token Refresh Request",
                value={
                    "refresh": "ak6ahags..."
                },
                request_only=True,
            ),
            OpenApiExample(
                "Token Refresh Response",
                value={
                    "access": "ak6ahags...",
                    "refresh": "ak6ahags..."
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


# View for Customer Profile
class CustomerProfileViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CustomerProfile.objects.filter(user=self.request.user)


# View for Driver Profile
class DriverProfileViewSet(viewsets.ModelViewSet):
    serializer_class = DriverProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return DriverProfile.objects.filter(user=self.request.user)
    
    
# View for Customer/Driver Registration request
class RegisterRequestAPIView(APIView):
    throttle_classes = [OTPRegisterThrottle]  # reuse throttle
    permission_classes = [AllowAny]  # Allow public access

    @extend_schema(
        tags=["Registration"],
        summary="Register Customer or Driver",
        description="Creates a registration request and sends OTP to email.",
        request=RegisterRequestSerializer,
        responses={
            201: OpenApiResponse(description="If valid email,OTP sent"),
            400: OpenApiResponse(description="Invalid request"),
        },
    )

    def post(self, request):

        serializer = RegisterRequestSerializer(data=request.data)
        if serializer.is_valid():
    
            user = serializer.save()

            send_otp(user, otp_purpose="registration")

            return Response(
                {"message": "If valid email, OTP sent"},
                status=status.HTTP_201_CREATED,
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

# View for otp verification for registration
class RegisterVerifyAPIView(APIView):
    throttle_classes = [OTPVerifyThrottle]

    @extend_schema(
        tags=["Registration"],
        summary="Verify Registration OTP",
        request=RegisterVerifySerializer,
        responses={
            200: OpenApiResponse(description="OTP verified"),
            400: OpenApiResponse(description="Invalid OTP"),
            403: OpenApiResponse(description="Too many attempts"),
        },
        examples=[
            OpenApiExample(
                "OTP Verification",
                value={
                    "email": "user@gmail.com",
                    "otp": "123456"
                },
                request_only=True,
            )
        ],
    )
    def post(self, request):

        serializer = RegisterVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        token = verify_otp(
            serializer.validated_data["email"], serializer.validated_data["otp"], "registration"
        )
        return Response({"register_token": token})
    

# View for Otp confirmation for registration
class RegisterConfirmAPIView(APIView):

    @extend_schema(
        tags=["Registration"],
        summary="Confirm Registration",
        request=RegisterConfirmSerializer,
        responses={201: OpenApiResponse(description="User registered")},
    )

    def post(self, request):

        serializer = RegisterConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        token = serializer.validated_data["register_token"]

        def activate(user):
            from rest_framework.exceptions import ValidationError
            if user.role not in [CustomUser.Role.CUSTOMER, CustomUser.Role.DRIVER]:
                raise ValidationError("Only customers and drivers can register publicly.")
            if user.email != serializer.validated_data["email"] or user.is_active:
                raise ValidationError("Invalid registration confirmation.")
            user.is_active = True
            user.save(update_fields=['is_active'])

        user = confirm_account_token(token, "registration", activate)

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


# View for role based profile update for Customer/Driver
class RoleBasedProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        tags=["Profiles"],
        summary="Get User Profile",
        responses={200: OpenApiResponse(description="User profile")},
    )
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
    
    @extend_schema(
        tags=["Profiles"],
        summary="Customer/Driver Porfile Update",
        description="Complete Profile for Customers/Drivers",
        request=PolymorphicProxySerializer(component_name="ProfileUpdate", serializers=[CustomerProfileSerializer, DriverProfileSerializer], resource_type_field_name=None),
        responses={200: OpenApiResponse(description="Profile Updated Successfully")},
        examples=[
            OpenApiExample(
                "Customer Profile Update Request",
                value={
                    "first_name": "Mark",
                    "last_name": "Tagoe",
                    "address": "a567/16 Dama Street"
                },
                request_only=True,
            ),
            OpenApiExample(
                "Driver Profile Update Request",
                value={
                    "first_name": "Issah",
                    "last_name": "Mussah",
                    "vehicle_type": "Royal Motor",
                    "vehicle_number": "MT-1076-22",
                    "license_number": "DV100188211222"
                },
                request_only=True,
            ),
            OpenApiExample(
                "Driver Profile Update Response",
                value={
                        "message": "Profile updated successfully"
                },
                response_only=True,
            ),
        ],
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

            return Response({
                "message": "Profile updated successfully",
                "profile": serializer.data
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# View for Driver approval after profile update is completed for admins
class DriverApprovalAPIView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        tags=["Admin"],
        summary="Driver Approval",
        description="Approve new drivers with valid details",
        request=DriverApprovalSerializer,
        responses={200: OpenApiResponse(description="Driver Approved successfully")},
        examples=[
            OpenApiExample(
                "New Driver Approval Confirmation",
                value={
                    "email": "user@gmail.com",
                    "action": "approve"
                },
                request_only=True,
            ),
            OpenApiExample(
                "New Driver Approval Response",
                value={
                        "message": "Driver *new approved successfully"
                },
                response_only=True,
            ),
        ],
    )

    def put(self, request):
        serializer = DriverApprovalSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        try:
            email = serializer.validated_data["email"]
            action = serializer.validated_data["action"]

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
            profile.rejection_reason = ""
        elif action == "reject":
            profile.approval_status = "rejected"
            profile.is_approved = False
            profile.rejection_reason = serializer.validated_data.get("rejection_reason", "")
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


# View for Password reset request
class PasswordResetRequestAPIView(APIView):
    throttle_classes = [OTPRegisterThrottle]  # reuse throttle
       
    @extend_schema(
        tags=["Password Reset"],
        summary="Password Reset Request",
        description="Password reset request for users.",
        request=PasswordResetRequestSerializer,
        responses={200: OpenApiResponse(description="If account exists, OTP sent")},
        examples=[
            OpenApiExample(
                "Password Reset Request",
                value={
                    "email": "user@gmail.com",
                },
                request_only=True,
            ),
            OpenApiExample(
                "Password Reset Request Response",
                value={
                    "message": "If account exists, OTP sent"
                },
                response_only=True,
            ),
        ],
    )


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

        send_otp(user, otp_purpose="password_reset")

        return Response({"message": "If account exists, OTP sent"})
    

# View for Password reset otp verification
class PasswordResetVerifyAPIView(APIView):
    throttle_classes = [OTPVerifyThrottle]


    @extend_schema(
        tags=["Password Reset"],
        summary="Password Reset Verify Otp",
        description="Verify Password Reset OTP",
        request=PasswordResetVerifySerializer,
        responses={200: OpenApiResponse(description="reset_token: eyJhbGci...")},
        examples=[
            OpenApiExample(
                "Password Reset OTP Verification",
                value={
                    "email": "user@gmail.com",
                    "otp": "987650"
                },
                request_only=True,
            ),
            OpenApiExample(
                "Verify Password Reset OTP Response",
                value={
                    "reset_token": "eyJhbGci..."
                },
                response_only=True,
            ),
        ],
    )

    def post(self, request):

        serializer = PasswordResetVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        token = verify_otp(
            serializer.validated_data["email"], serializer.validated_data["otp"], "password_reset"
        )
        return Response({"reset_token": token})
    

# View for Passord reset otp confirmation
class PasswordResetConfirmAPIView(APIView):

    @extend_schema(
        tags=["Password Reset"],
        summary="Confirm Password Reset Token",
        description="Confirm token for Password Reset",
        request=PasswordResetConfirmSerializer,
        responses={200: OpenApiResponse(description="Password Reset successful")},
        examples=[
            OpenApiExample(
                "Password Reset Token Confirmation",
                value={
                    "reset_token": "eyJhbGci...",
                    "new_password": "StrongerPassword"
                },
                request_only=True,
            ),
            OpenApiExample(
                "Password Reset Token Confirmation Response",
                value={
                        "message": "Password reset successful"
                },
                response_only=True,
            ),
        ],
    )

    def post(self, request):

        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        token = serializer.validated_data["reset_token"]
        new_password = serializer.validated_data["new_password"]

        def reset_password(user):
            from django.contrib.auth.password_validation import validate_password
            from django.core.exceptions import ValidationError as DjangoValidationError
            from rest_framework.exceptions import ValidationError
            try:
                validate_password(new_password, user=user)
            except DjangoValidationError as exc:
                raise ValidationError({"new_password": exc.messages})
            user.set_password(new_password)
            user.save(update_fields=['password'])

        confirm_account_token(token, "password_reset", reset_password)
        return Response({"message": "Password reset successful"})
