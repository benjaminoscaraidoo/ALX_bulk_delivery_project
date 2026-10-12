from rest_framework import serializers
from .models import Delivery, Payment
from order.models import Package, Order
from django.utils import timezone
from django.db import transaction

# Serializer for Delivery
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

# Serializer for Payment
class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = ("amount", "payment_status", "paid_at", "confirmed_by", "transaction_reference", "transaction_recorded_by", "transaction_recorded_at")


# Serializer for DeliveryItem
# Used in Creating deliveries serializer
class DeliveryItemSerializer(serializers.Serializer):
    package_id = serializers.PrimaryKeyRelatedField(
        queryset=Package.objects.all()
    )
    address = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        package = attrs["package_id"]

        request = self.context["request"]
        if package.order_id.customer_id != request.user:
            raise serializers.ValidationError("You can only create deliveries for your own packages.")

        if hasattr(package, "quote") and attrs.get("address") and attrs["address"] != package.quote.delivery_address:
            raise serializers.ValidationError("Delivery address must match the confirmed quote.")
        if package.delivery_address:
            attrs["address"] = package.delivery_address

        # Prevent duplicate delivery
        if hasattr(package, "deliveries"):
            raise serializers.ValidationError(
                f"Package {package.id} already has a delivery."
            )

        order = package.order_id  

        if not order.driver_id:
            raise serializers.ValidationError(
                f"Order {order.id} has no driver assigned."
            )

        attrs["rider"] = order.driver_id
        return attrs
    


# Serializer for Creating deliveries for multiple packages
class CreateDeliveriesSerializer(serializers.Serializer):
    deliveries = DeliveryItemSerializer(many=True)

    def create(self, validated_data):
        deliveries_data = validated_data["deliveries"]

        delivery_objects = []

        for item in deliveries_data:
            rider = item.pop("rider")
            package = item["package_id"]

            delivery_objects.append(
                Delivery(
                    package_id=package,
                    rider=rider,
                    address=item.get("address", "")
                )
            )

        created_deliveries = []

        for delivery in delivery_objects:
            delivery.save() 
            created_deliveries.append(delivery)

        return created_deliveries


# Serializer for Delivery status update by assigned driver/riders
class DriverDeliveryUpdateSerializer(serializers.Serializer):

    package_id = serializers.PrimaryKeyRelatedField(
        queryset=Package.objects.all(),
        source="package",
        write_only=True
    )

    delivery_status = serializers.CharField(required=True)
    delivery_notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        package = attrs["package"]
        request = self.context["request"]

        # Get delivery from package
        try:
            delivery = package.deliveries
        except Delivery.DoesNotExist:
            raise serializers.ValidationError("Delivery not found.")
        
                
        # Ensure delivery belongs to this rider
        if not delivery.rider or delivery.rider.user_id != request.user.pk:
            raise serializers.ValidationError(
                "You can only update deliveries assigned to you."
            )
        
        if package.order_id.order_status in [Order.Status.CANCELLED, Order.Status.DELIVERED]:
            raise serializers.ValidationError("Cannot update deliveries for a cancelled or completed order.")

        new_delivery_status = attrs["delivery_status"]
        current_status = delivery.delivery_status

        # Prevent rollback
        valid_transitions = {
            "assigned": ["picked_up"],
            "picked_up": ["delivered"],
            "delivered": []
        }

        if new_delivery_status not in valid_transitions.get(current_status, []):
            raise serializers.ValidationError(
                f"Invalid status transition from '{current_status}' to '{new_delivery_status}'."
            )

        attrs["delivery"] = delivery
        return attrs

    def create(self, validated_data):

        with transaction.atomic():

            order = Order.objects.select_for_update().get(
                pk=validated_data["delivery"].package_id.order_id_id
            )
            delivery = Delivery.objects.select_for_update().get(
                pk=validated_data["delivery"].pk
            )

            package = delivery.package_id
            package.deliveries = delivery
            package.order_id = order
            self.validate({**validated_data, "package": package})

            new_status = validated_data["delivery_status"]
            delivery.delivery_notes = validated_data.get("delivery_notes", "")

            if new_status == "picked_up":
                delivery.picked_up_at = timezone.now()

            if new_status == "delivered":
                delivery.delivered_at = timezone.now()

            delivery.delivery_status = new_status
            delivery.save()


            if new_status == "picked_up" and order.order_status != Order.Status.IN_TRANSIT:
                order.order_status = Order.Status.IN_TRANSIT
                order.save()

            total = order.packages.count()

            delivered_count = Delivery.objects.filter(
                package_id__order_id=order.id,
                delivery_status=Delivery.Status.DELIVERED
            ).count()

            if total > 0 and total == delivered_count:
                order.order_status = Order.Status.DELIVERED
                order.save()


        return delivery
