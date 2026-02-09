from rest_framework import serializers
from .models import CustomUser, CustomerProfile, DriverProfile


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = (
            "id",
            "email",
            "phone_number",
            "role",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class CustomerProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = CustomerProfile
        fields = "__all__"
        read_only_fields = ("user",)


class DriverProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = DriverProfile
        fields = "__all__"
        read_only_fields = ("user",)
