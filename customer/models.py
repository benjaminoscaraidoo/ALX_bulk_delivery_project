from django.db import models
from phonenumber_field.modelfields import PhoneNumberField
from django.contrib.auth.models import User, AbstractUser,BaseUserManager,PermissionsMixin
from django.conf import settings
from django.utils import timezone
import uuid

# Create your models here.


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
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", CustomUser.Role.ADMIN)

        return self.create_user(email,phone_number,password, **extra_fields)


class CustomUser(AbstractUser, PermissionsMixin):
    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        DRIVER = "driver", "Driver"
        ADMIN = "admin", "Admin"

    username = models.CharField(max_length=150, unique=True, blank=True, null=True)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["phone_number"]
    #phone_verified = models.BooleanField(default=False)
    #verification_token = models.CharField(max_length=6, null=True, blank=True)
    objects = CustomUserManager()

    def __str__(self):
        return self.email


class CustomerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer_profile")
    date_modified = models.DateTimeField(User, auto_now=True)
    customer_name = models.CharField(max_length=350, blank=True) 
    address = models.CharField(max_length=350, blank=True)
    is_complete = models.BooleanField(default=False)  


    def __str__(self):
        #return self.user.username
        return self.customer_name
	

# Create a user Profile by default when user signs up
#def create_profile(sender, instance, created, **kwargs):
#	if created:
#		user_profile = CustomerProfile(user=instance)
#		user_profile.save()


class DriverProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,  related_name="driverprofile")
    date_modified = models.DateTimeField(User, auto_now=True)
    vehicle_type = models.CharField(max_length=150, blank=True)
    vehicle_number = models.CharField(max_length=50, blank=True) 
    license_number = models.CharField(max_length=50, blank=True) 
    #phone = PhoneNumberField(unique=True, null=True, blank=True)
    availability_status = models.BooleanField(default=True)
    is_complete = models.BooleanField(default=False)
    

    def __str__(self):
          #return self.user.username
        return self.user.email