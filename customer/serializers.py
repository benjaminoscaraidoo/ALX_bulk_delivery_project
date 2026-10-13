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
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=20)
    role = serializers.ChoiceField(choices=[CustomUser.Role.CUSTOMER, CustomUser.Role.DRIVER])
    delivery_channel = serializers.ChoiceField(choices=["email", "sms"], default="email")
    password = serializers.CharField(write_only=True, required=True)
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = CustomUser
        fields = ["email", "phone_number", "role", "password" , "password2", "delivery_channel"]

    def validate_email(self, value):
        if not value:
            return None
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value
    
    def validate(self, attrs):
        from .sms import normalize_phone, check_sms_configuration
        if attrs.get("role") == "driver" and attrs["delivery_channel"] != "sms":
            raise serializers.ValidationError("Drivers must register using phone verification.")
        if attrs.get("phone_number"):
            attrs["phone_number"] = normalize_phone(attrs["phone_number"])
            if User.objects.filter(phone_number=attrs["phone_number"]).exists():
                raise serializers.ValidationError({"phone_number": "This phone number is already in use."})
        if attrs["delivery_channel"] == "sms":
            check_sms_configuration()
            if not attrs.get("phone_number"):
                raise serializers.ValidationError({"phone_number": "Phone number is required for SMS signup."})
        elif not attrs.get("email"):
            raise serializers.ValidationError({"email": "Email is required for email signup."})
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        

        validate_password(attrs["password"])
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")

        user = User.objects.create_user(
            email=validated_data.get("email"),
            phone_number=validated_data.get("phone_number"),
            role = validated_data.get("role"),
            password=validated_data["password"],
            is_active=False
        )

        return user
    

# Serializer for registration verification of otp, this is for both customer/drivers and super users
class AccountIdentifierSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(required=False)

    def validate(self, attrs):
        identifier = attrs.get('identifier') or attrs.get('email') or attrs.get('phone_number')
        if not identifier:
            raise serializers.ValidationError("Enter your phone number or email.")
        attrs['identifier'] = identifier.strip()
        return attrs


class RegisterVerifySerializer(AccountIdentifierSerializer):
    delivery_channel = serializers.ChoiceField(choices=['email', 'sms'], default='email')
    otp = serializers.CharField(max_length=6)


class RegisterConfirmSerializer(AccountIdentifierSerializer):
    register_token = serializers.CharField()


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
                if "phone_number" in user_data and user_data["phone_number"] != user.phone_number:
                    user.phone_verified = False
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
                    profile.is_complete = bool(profile.customer_name and profile.address.strip() and user.phone_number and user.phone_verified)
                else:
                    profile.is_complete = bool(user.first_name.strip() and user.last_name.strip() and user.phone_verified) and all(
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
        from .sms import normalize_phone
        value = normalize_phone(value) if value else None
        queryset = User.objects.filter(phone_number=value).exclude(pk=self.instance.user_id if self.instance else None) if value else User.objects.none()
        if queryset.exists():
            raise serializers.ValidationError("This phone number is already in use.")
        if self.instance and value != self.instance.user.phone_number:
            raise serializers.ValidationError("Verify the new phone through Login & recovery contacts before changing it.")
        return value


class DriverProfileSerializer(AtomicProfileSerializer):
    class Meta:
        model = DriverProfile
        fields = ["first_name", "last_name", "vehicle_type", "vehicle_number", "license_number", "availability_status", "is_complete"]
        read_only_fields = ["is_complete"]


# Serializer for JWT token generation for login
class MyTokenObtainPairSerializer(serializers.Serializer):
    identifier = serializers.CharField(required=False)
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(required=False)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        from django.contrib.auth import authenticate
        from rest_framework.exceptions import AuthenticationFailed
        from rest_framework_simplejwt.tokens import RefreshToken
        identifier = attrs.get('identifier') or attrs.get('email') or attrs.get('phone_number')
        user = authenticate(request=self.context.get('request'), username=identifier, password=attrs['password'])
        if not user:
            raise AuthenticationFailed('Invalid credentials or unverified contact.')
        refresh = RefreshToken.for_user(user)
        refresh['role'] = user.role
        profile = getattr(user, 'customer_profile', None) if user.role == 'customer' else getattr(user, 'driverprofile', None)
        return {'refresh': str(refresh), 'access': str(refresh.access_token), 'role': user.role,
                'profile_complete': bool(profile and profile.is_complete) if user.role != 'admin' else True}


# Serializer for Driver approval after registration and driver profile update
class DriverApprovalSerializer(AccountIdentifierSerializer):
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    rejection_reason = serializers.CharField(required=False, allow_blank=True)


# Serializer for User password reset request
class PasswordResetRequestSerializer(AccountIdentifierSerializer):
    delivery_channel = serializers.ChoiceField(choices=["email", "sms"], default="email")

    
# Serializer for User password otp verify
class PasswordResetVerifySerializer(AccountIdentifierSerializer):
    delivery_channel = serializers.ChoiceField(choices=["email", "sms"], default="email")
    otp = serializers.CharField(max_length=6)

# Serializer for User password otp confirm
class PasswordResetConfirmSerializer(serializers.Serializer):
    reset_token = serializers.CharField()
    new_password = serializers.CharField(min_length=8, write_only=True)


# Serializer for otp verification
class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)



class RegisterResendSerializer(AccountIdentifierSerializer):
    password = serializers.CharField(write_only=True)
    delivery_channel = serializers.ChoiceField(choices=['email', 'sms'], default='email')
