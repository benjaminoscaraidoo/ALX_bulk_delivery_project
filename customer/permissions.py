from rest_framework.permissions import BasePermission, SAFE_METHODS


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
