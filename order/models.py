from django.db import models
from customer.models import DriverProfile
import datetime
from django.conf import settings
from .utils import generate_order_id, generate_package_id

# Create your models here.

# Models for Order
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
    cancel_reason = models.CharField(max_length=350, blank=True)
    created_at = models.DateField(default=datetime.datetime.today)

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = generate_order_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.id}" 
    

# Models for Packages
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
    receiver_phone = models.CharField(max_length=20, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = generate_package_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.id