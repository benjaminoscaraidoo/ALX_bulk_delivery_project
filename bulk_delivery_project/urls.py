"""
URL configuration for bulk_delivery_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from rest_framework.routers import DefaultRouter
from customer.views import CustomerProfileViewSet, DriverProfileViewSet
from delivery.views import DeliveryViewSet,PaymentViewSet
from order.views import OrderViewSet, PackageViewSet
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)



router = DefaultRouter()
router.register(r"profiles/customer", CustomerProfileViewSet, basename="customer-profile")
router.register(r"profiles/driver", DriverProfileViewSet, basename="driver-profile")
router.register(r"deliveries", DeliveryViewSet, basename="deliveries")
router.register(r"payments", PaymentViewSet, basename="payments")
router.register(r"orders", OrderViewSet, basename="orders")
router.register(r"packages", PackageViewSet, basename="packages")



urlpatterns = [
    path('admin/', admin.site.urls),


  # JWT Auth
    path("api/v1/auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/v1/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),

        
    path('api/v1/', include(router.urls)),
    path('', include('customer.urls')),
    #path('api/v1/', include('order.urls')),
    #path('api/v1/', include('delivery.urls')),
]



