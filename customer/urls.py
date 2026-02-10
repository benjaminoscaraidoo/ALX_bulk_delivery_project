from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import CustomerProfileViewSet, DriverProfileViewSet
from . import views

#router = DefaultRouter()
#router.register(r"profiles/customer", CustomerProfileViewSet, basename="customer-profile")
#router.register(r"profiles/driver", DriverProfileViewSet, basename="driver-profile")


urlpatterns = [
#path('', include(router.urls)),
path('', views.home, name='home'),
]