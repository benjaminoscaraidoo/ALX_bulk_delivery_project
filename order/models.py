from django.db import models
from customer.models import CustomerProfile,DriverProfile
import datetime
from phonenumber_field.modelfields import PhoneNumberField


# Create your models here.
class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        ASSIGNED = "assigned"
        IN_TRANSIT = "in_transit"
        DELIVERED = "delivered"
        CANCELLED = "cancelled"

    customer_id = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name="orders")
    delivery_date = models.DateField(blank=True)
    driver_id = models.OneToOneField(DriverProfile, on_delete=models.CASCADE, default=None)
    pickup_address = models.CharField(max_length=350, blank=True) 
    total_price = models.FloatField(default=0.0)
    order_status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateField(default=datetime.datetime.today)

    
    def __str__(self):
        return f"Order #{self.id}" 
    

class Package(models.Model):
    order_id = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="packages")
    description = models.CharField(max_length=150, blank=True)
    dimensions = models.CharField(max_length=50, blank=True)  
    value = models.FloatField(default=0.0)
    fragile = models.BooleanField(default=False)
    receiver_name = models.CharField(max_length=350, blank=True)
    receiver_phone = PhoneNumberField(null=True, blank=True)

    def __str__(self):
        return self.description