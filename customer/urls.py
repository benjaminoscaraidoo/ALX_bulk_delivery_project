from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import (
    session_login,
    login_view,
    register_view,
    logout_view,
    update_profile,
    update_password,
    update_user,
    driver_home,
    home,
    MyTokenObtainPairView)
from . import views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)


app_name = "customer"

urlpatterns = [
    #path('', include(router.urls)),
    #path('', views.home, name='home'),
    path('home/', home, name='home'),
    path("driver-home/", driver_home, name="driver_home"), 
    path("login/", login_view, name="login"),
    path("session-login/", session_login, name="session_login"),
    path("register/", register_view, name="register"),
    path("update-profile/", update_profile, name="update_profile"),
    path('update_password/', update_password, name='update_password'),
    path('update_user/', update_user, name='update_user'),
    path("logout/", logout_view, name="logout"),


      # JWT Auth
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("api/v1/auth/login/", MyTokenObtainPairView.as_view(), name="token_obtain_pair"),
]