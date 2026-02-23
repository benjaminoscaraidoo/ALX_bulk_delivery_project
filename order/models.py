from django.db import models
from customer.models import CustomerProfile,DriverProfile
import datetime
import uuid
from django.conf import settings
from phonenumber_field.modelfields import PhoneNumberField


# Create your models here.

def generate_package_id():
    return f"PKG{uuid.uuid4().hex[:8].upper()}"

def generate_order_id():
    return f"ORD{uuid.uuid4().hex[:8].upper()}"

class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        ASSIGNED = "assigned"
        IN_TRANSIT = "in_transit"
        DELIVERED = "delivered"
        CANCELLED = "cancelled"
        
    id = models.CharField(
        primary_key=True,
        max_length=12,
        editable=False
    )
    customer_id = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    delivery_date = models.DateField(null=True,blank=True)
    #driver_id = models.OneToOneField(DriverProfile, on_delete=models.CASCADE,null=True, default=None)
    driver_id = models.ForeignKey(
    DriverProfile,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="dorders"
)
    pickup_address = models.CharField(max_length=350, null=True,blank=True) 
    total_price = models.FloatField(default=0.0)
    order_status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateField(default=datetime.datetime.today)

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = generate_order_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.id}" 
    


class Package(models.Model):
    id = models.CharField(
        primary_key=True,
        max_length=12,
        editable=False
    )
    order_id = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="packages")
    description = models.CharField(max_length=150, blank=True)
    dimensions = models.CharField(max_length=50, blank=True)  
    value = models.FloatField(default=0.0)
    fragile = models.BooleanField(default=False)
    receiver_name = models.CharField(max_length=350, blank=True)
    receiver_phone = PhoneNumberField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = generate_package_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.id