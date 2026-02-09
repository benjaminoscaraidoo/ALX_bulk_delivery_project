from django.db import models
from phonenumber_field.modelfields import PhoneNumberField
from django.contrib.auth.models import User, AbstractUser,BaseUserManager,PermissionsMixin
from django.conf import settings
from django.utils import timezone

# Create your models here.


class CustomUserManager(BaseUserManager):
    def create_user(self,phone_number,email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Username must be set")

        email = self.normalize_email(email)
        user = self.model(
            email = email,
            phone_number = phone_number
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self,phone_number,email=None, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", True)

        return self.create_user(email,phone_number,password, **extra_fields)


class CustomUser(AbstractUser, PermissionsMixin):
    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        DRIVER = "driver", "Driver"
        ADMIN = "admin", "Admin"

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


#    def save(self, *args, **kwargs):
#        self.email = self.user.email
#        super().save(*args, **kwargs)


    def __str__(self):
        #return self.user.username
        return self.customer_name
	

# Create a user Profile by default when user signs up
#def create_profile(sender, instance, created, **kwargs):
#	if created:
#		user_profile = CustomerProfile(user=instance)
#		user_profile.save()


class DriverProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date_modified = models.DateTimeField(User, auto_now=True)
    vehicle_type = models.CharField(max_length=150, blank=True)
    vehicle_number = models.CharField(max_length=50, blank=True) 
    license_number = models.CharField(max_length=50, blank=True) 
    phone = PhoneNumberField(unique=True, null=True, blank=True)
    availability_status = models.BooleanField(default=True)
    

    def __str__(self):
          #return self.user.username
        return self.user.email