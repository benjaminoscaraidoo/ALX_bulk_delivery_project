from rest_framework.permissions import BasePermission, SAFE_METHODS
from .models import CustomerProfile

class IsAdmin(BasePermission):
    """
    Allows access only to admin users
    """

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == "admin"
        )


class IsCustomer(BasePermission):
    """
    Allows access only to customers
    """

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == "customer"
        )


class IsDriver(BasePermission):
    """
    Allows access only to drivers
    """

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == "driver"
        )

class IsOrderOwnerOrAdmin(BasePermission):
    """
    Object-level permission for Order
    """

    def has_object_permission(self, request, view, obj):
        return (
            request.user.role == "admin"
            or obj.customer == request.user
        )


class IsAssignedDriverOrAdmin(BasePermission):
    """
    Object-level permission for Delivery
    """

    def has_object_permission(self, request, view, obj):
        return (
            request.user.role == "admin"
            or obj.driver == request.user
        )


class IsCustomerProfileComplete(BasePermission):
    """
    Permission to allow only customers with completed profiles to create orders.
    """
    def has_permission(self, request, view):
        user = request.user

        if not user.is_authenticated:
            self.message = "Authentication credentials were not provided."
            return False

        if user.role != "customer":
            self.message = "Only customers can create orders."
            return False

        try:
            profile = user.customer_profile
            if not profile.is_complete:
                self.message = "Complete your profile before creating orders."
                return False
        except CustomerProfile.DoesNotExist:
            self.message = "Customer profile not found. Please complete your profile."
            return False

        return True