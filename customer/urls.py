from django.urls import path
from .views import (
    MyTokenObtainPairView,
    MyTokenVerifyView,
    RegisterRequestAPIView,
    RoleBasedProfileAPIView,
    DriverApprovalAPIView,
    RegisterSuperUserRequestAPIView,
    PasswordResetRequestAPIView,
    PasswordResetVerifyAPIView,
    PasswordResetConfirmAPIView,
    RegisterVerifyAPIView,
    RegisterConfirmAPIView,
    MyTokenRefreshView,
    api_root)



app_name = "customer"

urlpatterns = [
    path("v1", api_root),
    path("v1/register/request/", RegisterRequestAPIView.as_view(), name="api-register"),
    path("v1/register/verify/", RegisterVerifyAPIView.as_view(), name="api-register-verify"),
    path("v1/register/confirm/", RegisterConfirmAPIView.as_view(), name="api-register-confirm"),
    path("v1/password-reset/request/", PasswordResetRequestAPIView.as_view(), name="password-reset-request"),
    path("v1/password-reset/verify/", PasswordResetVerifyAPIView.as_view(), name="password-reset-verify"),
    path("v1/password-reset/confirm/", PasswordResetConfirmAPIView.as_view(), name="password-reset-confirm"),
    path("v1/register/request/superuser/", RegisterSuperUserRequestAPIView.as_view(), name="api_register_superuser"),
    path("v1/profile/update/", RoleBasedProfileAPIView.as_view(), name="api_role_profile"),
    path("v1/admin/driver/approve/", DriverApprovalAPIView.as_view(), name="driver_approval"),

      # JWT Auth
    path("v1/auth/token/refresh/", MyTokenRefreshView.as_view(), name="token_refresh"),
    path("v1/auth/token/verify/", MyTokenVerifyView.as_view(), name="token_verify"),
    path("v1/auth/login/", MyTokenObtainPairView.as_view(), name="token_obtain_pair"),
]