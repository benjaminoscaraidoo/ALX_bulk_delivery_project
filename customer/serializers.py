from rest_framework import serializers
from .models import CustomUser, CustomerProfile, DriverProfile
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


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


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['role'] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # Include role in response
        data['role'] = self.user.role
        # Optionally include profile completion status
        if self.user.role == CustomUser.Role.CUSTOMER:
            data['profile_complete'] = bool(self.user.customer_profile.customer_name)
        elif self.user.role == CustomUser.Role.DRIVER:
            profile = getattr(self.user, "driverprofile", None)
            data['profile_complete'] = bool(profile and profile.vehicle_type)
        else:
            data['profile_complete'] = True
        return data
