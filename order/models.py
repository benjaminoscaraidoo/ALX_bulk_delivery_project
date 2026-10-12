from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
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
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
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
    value = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    fragile = models.BooleanField(default=False)
    delivery_address = models.CharField(max_length=350, blank=True)
    outside_accra = models.BooleanField(default=False)
    delivery_area = models.ForeignKey("DeliveryArea", null=True, blank=True, on_delete=models.PROTECT)
    receiver_name = models.CharField(max_length=350, blank=True)
    receiver_phone = models.CharField(max_length=20, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = generate_package_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.id

class DistanceTariff(models.Model):
    upper_km = models.DecimalField(max_digits=8, decimal_places=3, unique=True, validators=[MinValueValidator(Decimal('0.001'))])
    charge = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ['upper_km']

    def __str__(self):
        return f"Up to {self.upper_km} km: GHS {self.charge}"


class DeliveryArea(models.Model):
    name = models.CharField(max_length=150, unique=True)
    charge = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class DeliveryQuote(models.Model):
    package = models.OneToOneField(Package, on_delete=models.PROTECT, related_name='quote')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    distance_meters = models.PositiveIntegerField(null=True, blank=True)
    pickup_address = models.CharField(max_length=350)
    delivery_address = models.CharField(max_length=350)
    outside_accra = models.BooleanField()
    area_name = models.CharField(max_length=150, blank=True)
    reason = models.CharField(max_length=350)
    created_at = models.DateTimeField(auto_now_add=True)
