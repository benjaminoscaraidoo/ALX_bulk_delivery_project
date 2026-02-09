from django.db import models
from customer.models import CustomerProfile
import datetime


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
    pickup_address = models.CharField(max_length=350, blank=True) 
    total_price = models.FloatField(default=0)
    order_status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateField(default=datetime.datetime.today)

    
    def __str__(self):
        return f"Order #{self.id}" 
    

class Package(models.Model):
    order_id = models.ForeignKey(Order, on_delete=models.CASCADE)
    description = models.CharField(max_length=150, blank=True)
    dimensions = models.CharField(max_length=50, blank=True)  
    value = models.FloatField(default=0.0)
    fragile = models.BooleanField(default=False)


    
    def __str__(self):
        return self.description