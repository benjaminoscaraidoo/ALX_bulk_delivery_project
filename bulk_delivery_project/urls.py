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
#from . import views
from delivery.views import DeliveryViewSet,PaymentViewSet
from order.views import OrderViewSet, PackageViewSet



router = DefaultRouter()
router.register(r"profiles/customer", CustomerProfileViewSet, basename="customer-profile")
router.register(r"profiles/driver", DriverProfileViewSet, basename="driver-profile")
router.register(r"deliveries", DeliveryViewSet, basename="deliveries")
router.register(r"payments", PaymentViewSet, basename="payments")
router.register(r"orders", OrderViewSet, basename="orders")
router.register(r"packages", PackageViewSet, basename="packages")



urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/v1/', include(router.urls)),
    path('', include('customer.urls')),
    path('', include('order.urls')),
    path('', include('delivery.urls')),
]



