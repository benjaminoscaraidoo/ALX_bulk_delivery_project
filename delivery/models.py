from django.db import models
from order.models import Package
import datetime
import uuid
from customer.models import DriverProfile

# Create your models here.

def generate_delivery_id():
    return f"DEL{uuid.uuid4().hex[:8].upper()}"

def generate_transaction_id():
    return f"TXN{uuid.uuid4().hex[:8].upper()}"


class Delivery(models.Model):

    class Status(models.TextChoices):
        ASSIGNED = "assigned"
        PICKED_UP = "picked_up"
        DELIVERED = "delivered"
    id = models.CharField(
        primary_key=True,
        max_length=12,
        editable=False
    )
    package_id =  models.OneToOneField(Package, default=None, on_delete=models.CASCADE,related_name="deliveries")
    assigned_at = models.DateTimeField(auto_now_add=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    address = models.CharField(max_length=350, blank=True)
    delivery_status =  models.CharField(max_length=20,choices=Status.choices,default=Status.ASSIGNED) 
    delivery_notes = models.CharField(max_length=350, blank=True)

    rider = models.ForeignKey(
        DriverProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_deliveries"
    )
    
    def save(self, *args, **kwargs):
        if not self.id:
            self.id = generate_delivery_id()
        super().save(*args, **kwargs)


    def __str__(self):
        return self.id
    


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        PAID = "paid"
        FAILED = "failed"

    class Method(models.TextChoices):
        CASH = "cash"
        MOBILE_MONEY = "mobile_money"
        
    id = models.CharField(
        primary_key=True,
        max_length=12,
        editable=False
    )
    package_id = models.OneToOneField(Package, default=None, on_delete=models.CASCADE,related_name="payment")
    amount = models.FloatField(default=0.0)
    payment_method = models.CharField(max_length=20, choices=Method.choices)
    transaction_reference = models.CharField(max_length=150, blank=True)
    paid_at = models.DateField(null=True,blank=True)
    payment_status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING) 

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = generate_transaction_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.transaction_reference

