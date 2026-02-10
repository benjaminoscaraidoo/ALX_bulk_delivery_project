from django.shortcuts import render
from rest_framework import viewsets, permissions
from .models import CustomerProfile, DriverProfile
from django.views import View
from .serializers import (CustomerProfileSerializer,DriverProfileSerializer)
# Create your views here.

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
    

def home(request):
    return render(request, 'customer/home.html',{})

class Index(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'customer/index.html')
    
class About(View):
    def get(self, request, *args, **kwargs):
        return render(request, 'customer/about.html')
