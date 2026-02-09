from rest_framework import serializers
from .models import Delivery, Payment


class DeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = Delivery
        fields = "__all__"
        read_only_fields = (
            "assigned_at",
            "picked_up_at",
            "delivered_at",
            "delivery_status",
        )

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = ("status", "paid_at")