from rest_framework import serializers
from .models import CustomUser, CustomerProfile, DriverProfile
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from django.contrib.auth.password_validation import validate_password
User = get_user_model()

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


# Serializer for Customer/Driver registration request
class RegisterRequestSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=[CustomUser.Role.CUSTOMER, CustomUser.Role.DRIVER])
    password = serializers.CharField(write_only=True, required=True)
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = CustomUser
        fields = ["email", "phone_number", "role", "password" , "password2"]

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
            is_active=False
        )

        return user
    

# Serializer for registration verification of otp, this is for both customer/drivers and super users
class RegisterVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)


# Serializer for registration verification of otp, this is for both customer/drivers and super users  
class RegisterConfirmSerializer(serializers.Serializer):
    register_token = serializers.CharField()
    email = serializers.EmailField()


# Serializer for Customer profile update after registration

class AtomicProfileSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source="user.first_name", max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(source="user.last_name", max_length=150, required=False, allow_blank=True)

    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        try:
            with transaction.atomic():
                user = User.objects.select_for_update().get(pk=instance.user_id)
                profile = self.Meta.model.objects.select_for_update().get(pk=instance.pk)
                profile.user = user
                if "phone_number" in user_data:
                    self.validate_phone_number(user_data["phone_number"])
                for attr, value in user_data.items():
                    setattr(user, attr, value)
                user.save()
                changed_credentials = isinstance(profile, DriverProfile) and any(
                    field in validated_data and validated_data[field] != getattr(profile, field)
                    for field in ("vehicle_type", "vehicle_number", "license_number")
                )
                for attr, value in validated_data.items():
                    setattr(profile, attr, value)
                if isinstance(profile, CustomerProfile):
                    profile.customer_name = " ".join(part for part in (user.first_name.strip(), user.last_name.strip()) if part)
                    profile.is_complete = bool(profile.customer_name and profile.address.strip())
                else:
                    profile.is_complete = all(
                        getattr(profile, field).strip()
                        for field in ("vehicle_type", "vehicle_number", "license_number")
                    )
                    if changed_credentials:
                        profile.approval_status = "pending"
                        profile.is_approved = False
                        profile.rejection_reason = ""
                profile.save()
                return profile
        except IntegrityError:
            raise serializers.ValidationError({"phone_number": "This phone number is already in use."})


class CustomerProfileSerializer(AtomicProfileSerializer):
    phone_number = serializers.CharField(source="user.phone_number", max_length=20, required=False, allow_blank=True)

    class Meta:
        model = CustomerProfile
        fields = ["first_name", "last_name", "phone_number", "address", "is_complete"]
        read_only_fields = ["is_complete"]

    def validate_phone_number(self, value):
        # Clearing an optional phone must use NULL rather than a shared empty string.
        if not value:
            return None
        queryset = User.objects.filter(phone_number=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.user_id)
        if queryset.exists():
            raise serializers.ValidationError("This phone number is already in use.")
        return value


class DriverProfileSerializer(AtomicProfileSerializer):
    class Meta:
        model = DriverProfile
        fields = ["first_name", "last_name", "vehicle_type", "vehicle_number", "license_number", "availability_status", "is_complete"]
        read_only_fields = ["is_complete"]


# Serializer for JWT token generation for login
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
            profile = getattr(self.user, 'customer_profile', None)
            data['profile_complete'] = bool(profile and profile.is_complete)
        elif self.user.role == CustomUser.Role.DRIVER:
            profile = getattr(self.user, "driverprofile", None)
            data['profile_complete'] = bool(profile and profile.is_complete)
        else:
            data['profile_complete'] = True
        return data


# Serializer for Driver approval after registration and driver profile update
class DriverApprovalSerializer(serializers.Serializer):
    email = serializers.EmailField()
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    rejection_reason = serializers.CharField(required=False, allow_blank=True)


# Serializer for User password reset request
class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()    

    
# Serializer for User password otp verify
class PasswordResetVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

# Serializer for User password otp confirm
class PasswordResetConfirmSerializer(serializers.Serializer):
    reset_token = serializers.CharField()
    new_password = serializers.CharField(min_length=8, write_only=True)


# Serializer for otp verification
class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

