from rest_framework import serializers
from .models import CustomUser, CustomerProfile, DriverProfile
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.db import transaction
from django.contrib.auth.password_validation import validate_password
User = get_user_model()

class CustomerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerProfile
        fields = [
            "customer_name",
            "address",
            "is_complete",
        ]
        read_only_fields = ["is_complete"]


class DriverProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverProfile
        fields = [
            "vehicle_type",
            "vehicle_number",
            "license_number",
            "availability_status",
            "is_complete",
        ]
        read_only_fields = ["is_complete"]

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "phone_number",
        )
        read_only_fields = ("id", "email")


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = CustomUser
        fields = ["email", "phone_number","role", "password", "password2"]

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})

        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")

        user = User.objects.create_user(
            email=validated_data["email"],
            phone_number=validated_data.get("phone_number"),
            role = validated_data.get("role"),
            password=validated_data["password"],
        )

        return user


class RegisterSuperUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = CustomUser
        fields = ["email", "phone_number", "password", "password2","first_name","last_name",]

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})

        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")

        user = User.objects.create_superuser(
            email=validated_data["email"],
            first_name=validated_data["first_name"],
            last_name=validated_data["last_name"],
            phone_number=validated_data.get("phone_number"),
            password=validated_data["password"],
        )

        return user
    
    

class CustomerProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="user.first_name", required=False)
    last_name = serializers.CharField(source="user.last_name", required=False)
    phone_number = serializers.CharField(source="user.phone_number", required=False)

    class Meta:
        model = CustomerProfile
        fields = [
            "first_name",
            "last_name",
            "phone_number",
            "address",
            "is_complete",
        ]
        read_only_fields = ["is_complete"]

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})

        # Update User model fields
        if "first_name" in user_data:
            instance.user.first_name = user_data["first_name"]

        if "last_name" in user_data:
            instance.user.last_name = user_data["last_name"]

        if "phone_number" in user_data:
            instance.user.phone_number = user_data["phone_number"]

            

        instance.user.save()

        # Update profile fields

        instance.customer_name = instance.user.first_name + instance.user.last_name

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class DriverProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="user.first_name", required=False)
    last_name = serializers.CharField(source="user.last_name", required=False)

    class Meta:
        model = DriverProfile
        fields = [
            "first_name",
            "last_name",
            "vehicle_type",
            "vehicle_number",
            "license_number",
            "availability_status",
            "is_complete",
        ]
        read_only_fields = ["is_complete"]

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})

        # Update User fields
        if "first_name" in user_data:
            instance.user.first_name = user_data["first_name"]

        if "last_name" in user_data:
            instance.user.last_name = user_data["last_name"]

        instance.user.save()

        # Update profile fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['role'] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user
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


class DriverApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = DriverProfile
        fields = ["approval_status", "rejection_reason"]



class ResetPasswordSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True)
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = CustomUser
        fields = ["email","password", "password2"]

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        

        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):

        with transaction.atomic():

            user = CustomUser.objects.select_for_update().get(
                pk=validated_data["user"].pk
            )
            user.password=validated_data["password"]

            user.save()
    
        return user
    

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    
class PasswordResetVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

class PasswordResetConfirmSerializer(serializers.Serializer):
    reset_token = serializers.CharField()
    new_password = serializers.CharField(min_length=8)

    
class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

