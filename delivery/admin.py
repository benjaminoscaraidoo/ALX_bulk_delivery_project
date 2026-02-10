from django.contrib import admin
from .models import Delivery,Payment
# Register your models here.
@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ("order_id", "driver_id", "delivery_status", "assigned_at")
    list_filter = ("delivery_status",)
    search_fields = ("order__id", "driver__email")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order_id", "amount", "payment_method", "payment_status", "paid_at")
    list_filter = ("payment_method", "payment_status")
    search_fields = ("transaction_reference",)