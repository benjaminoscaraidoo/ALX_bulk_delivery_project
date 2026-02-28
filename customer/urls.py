from django.urls import path
from .views import (
    MyTokenObtainPairView,
    RegisterAPIView,
    RoleBasedProfileAPIView,
    DriverApprovalAPIView,
    RegisterSuperUserAPIView,
    ResetPasswordAPIView,
    VerifyOTPAPIView,
    PasswordResetRequestAPIView,
    PasswordResetVerifyAPIView,
    PasswordResetConfirmAPIView,)
from . import views
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)


app_name = "customer"

urlpatterns = [
    path("api/v1/register/", RegisterAPIView.as_view(), name="api_register"),
    path("api/v1/password-reset/request/", PasswordResetRequestAPIView.as_view(), name="password-reset-request"),
    path("api/v1/password-reset/verify/", PasswordResetVerifyAPIView.as_view(), name="password-reset-verify"),
    path("api/v1/password-reset/confirm/", PasswordResetConfirmAPIView.as_view(), name="password-reset-confirm"),
    path("api/v1/register_superuser/", RegisterSuperUserAPIView.as_view(), name="api_register_superuser"),
    path("api/v1/profile/update/", RoleBasedProfileAPIView.as_view(), name="api_role_profile"),
    path("api/v1/admin/driver/approve/", DriverApprovalAPIView.as_view(), name="driver_approval"),
    path("verify-otp/", VerifyOTPAPIView.as_view()),

      # JWT Auth
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("api/v1/auth/login/", MyTokenObtainPairView.as_view(), name="token_obtain_pair"),
]