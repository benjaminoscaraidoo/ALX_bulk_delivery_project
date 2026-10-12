from django.db import models
from django.core.validators import MinValueValidator
from order.models import Package
import datetime
from .utils import generate_delivery_id, generate_transaction_id
from customer.models import DriverProfile

# Create your models here.


# Model for Delivery
# This is linked to the Package for the orders
class Delivery(models.Model):

    class Status(models.TextChoices):
        ASSIGNED = "assigned"
        PICKED_UP = "picked_up"
        DELIVERED = "delivered"
        CANCELLED = "cancelled"
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
    

# Model for Payment
# This is linked to the Package for the orders
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
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    payment_method = models.CharField(max_length=20, choices=Method.choices)
    transaction_reference = models.CharField(max_length=150, blank=True)
    transaction_recorded_by = models.ForeignKey("customer.CustomUser", null=True, blank=True, on_delete=models.SET_NULL, related_name="recorded_payment_references")
    transaction_recorded_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey("customer.CustomUser", null=True, blank=True, on_delete=models.SET_NULL)
    paid_at = models.DateField(null=True,blank=True)
    payment_status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING) 

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['transaction_reference'],
                condition=models.Q(payment_status='paid') & ~models.Q(transaction_reference=''),
                name='unique_paid_transaction_reference'),
            models.CheckConstraint(condition=models.Q(amount__gte=0), name='nonnegative_payment_amount'),
        ]

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = generate_transaction_id()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.transaction_reference

