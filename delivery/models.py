from django.db import models
from order.models import Package
import datetime


# Create your models here.
class Delivery(models.Model):

    class Status(models.TextChoices):
        ASSIGNED = "assigned"
        PICKED_UP = "picked_up"
        DELIVERED = "delivered"

    package_id =  models.OneToOneField(Package, default=None, on_delete=models.CASCADE,related_name="deliveries")
    assigned_at = models.DateField(auto_now_add=True)
    picked_up_at = models.DateField(null=True, blank=True)
    delivered_at = models.DateField(null=True, blank=True)
    delivery_status =  models.CharField(max_length=20,choices=Status.choices,default=Status.ASSIGNED) 
    
    def __str__(self):
        #return self.delivery_status
        return f"Delivery for Order {self.order.id}"
    


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        PAID = "paid"
        FAILED = "failed"

    class Method(models.TextChoices):
        CASH = "cash"
        MOBILE_MONEY = "mobile_money"

    package_id = models.OneToOneField(Package, default=None, on_delete=models.CASCADE,related_name="payment")
    amount = models.FloatField(default=0.0)
    payment_method = models.CharField(max_length=20, choices=Method.choices)
    transaction_reference = models.CharField(max_length=150, blank=True)
    paid_at = models.DateField(null=True,blank=True)
    payment_status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING) 
    
    def __str__(self):
        return self.transaction_reference

