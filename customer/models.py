from django.db import models
from django.contrib.auth.models import AbstractUser,BaseUserManager,PermissionsMixin
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import uuid
from django.contrib.auth import get_user_model

# Create your models here.

#Custom BaseUserManager 

class CustomUserManager(BaseUserManager):
    def create_user(self,email,phone_number,password=None, **extra_fields):
        if not email:
            raise ValueError("The Email must be set")
        

        # Auto-generate username if not provided
        if not extra_fields.get("username"):
            extra_fields["username"] = f"user_{str(uuid.uuid4())[:8]}"

        email = self.normalize_email(email)

        user = self.model(
            email = email,
            phone_number = phone_number,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self,email,phone_number, password=None, **extra_fields):

        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", False)
        extra_fields.setdefault("role", CustomUser.Role.ADMIN)

        return self.create_user(email,phone_number,password, **extra_fields)


# Customer User model 
class CustomUser(AbstractUser, PermissionsMixin):
    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        DRIVER = "driver", "Driver"
        ADMIN = "admin", "Admin"

    username = models.CharField(max_length=150, unique=True, blank=True, null=True)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone_number"]

    objects = CustomUserManager()

    def __str__(self):
        return self.email


#CustomerProfile model for customers

class CustomerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer_profile")
    date_modified = models.DateTimeField(auto_now=True)
    customer_name = models.CharField(max_length=350, blank=True) 
    address = models.CharField(max_length=350, blank=True)
    is_complete = models.BooleanField(default=False)  


    def __str__(self):
        return self.customer_name
	

#DriverProfile model for riders/drivers

class DriverProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,  related_name="driverprofile")
    date_modified = models.DateTimeField(auto_now=True)
    vehicle_type = models.CharField(max_length=150, blank=True)
    vehicle_number = models.CharField(max_length=50, blank=True) 
    license_number = models.CharField(max_length=50, blank=True) 
    availability_status = models.BooleanField(default=True)
    is_complete = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    approval_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="pending"
    )
    rejection_reason = models.TextField(blank=True, null=True)
    

    def __str__(self):
        return f"{self.user.email} - {self.approval_status}"
    

#OTP Model for Email
class EmailOTP(models.Model):

    class Purpose(models.TextChoices):
        REGISTRATION = "registration", "Registration"
        PASSWORDRESET = "password_reset", "Password Reset"

    User = get_user_model()

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    otp_purpose = models.CharField(max_length=20, choices=Purpose.choices,default=False)  

    attempt_count = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)

    def is_expired(self):

        return timezone.now() - self.created_at > timedelta(minutes=5)

    def is_locked(self):
        return self.attempt_count >= self.max_attempts

    def __str__(self):
        return f"{self.user.email} - {self.otp}"