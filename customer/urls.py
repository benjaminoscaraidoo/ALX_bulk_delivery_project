from django.urls import path
from .views import (
    MyTokenObtainPairView,
    RegisterRequestAPIView,
    RoleBasedProfileAPIView,
    DriverApprovalAPIView,
    RegisterSuperUserRequestAPIView,
    PasswordResetRequestAPIView,
    PasswordResetVerifyAPIView,
    PasswordResetConfirmAPIView,
    RegisterVerifyAPIView,
    RegisterConfirmAPIView)
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)


app_name = "customer"

urlpatterns = [
    path("api/v1/register/request/", RegisterRequestAPIView.as_view(), name="api-register"),
    path("api/v1/register/verify/", RegisterVerifyAPIView.as_view(), name="api-register-verify"),
    path("api/v1/register/confirm/", RegisterConfirmAPIView.as_view(), name="api-register-confirm"),
    path("api/v1/password-reset/request/", PasswordResetRequestAPIView.as_view(), name="password-reset-request"),
    path("api/v1/password-reset/verify/", PasswordResetVerifyAPIView.as_view(), name="password-reset-verify"),
    path("api/v1/password-reset/confirm/", PasswordResetConfirmAPIView.as_view(), name="password-reset-confirm"),
    path("api/v1/register_superuser/", RegisterSuperUserRequestAPIView.as_view(), name="api_register_superuser"),
    path("api/v1/profile/update/", RoleBasedProfileAPIView.as_view(), name="api_role_profile"),
    path("api/v1/admin/driver/approve/", DriverApprovalAPIView.as_view(), name="driver_approval"),

      # JWT Auth
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("api/v1/auth/login/", MyTokenObtainPairView.as_view(), name="token_obtain_pair"),
]