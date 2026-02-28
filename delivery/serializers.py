from rest_framework import serializers
from django.shortcuts import get_object_or_404
from .models import Delivery, Payment
from order.models import Package, Order
from datetime import datetime
from django.db import transaction

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



class DeliveryItemSerializer(serializers.Serializer):
    package_id = serializers.PrimaryKeyRelatedField(
        queryset=Package.objects.all()
    )
    address = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        package = attrs["package_id"]

        # Prevent duplicate delivery
        if hasattr(package, "deliveries"):
            raise serializers.ValidationError(
                f"Package {package.id} already has a delivery."
            )

        order = package.order_id  # adjust if your field name differs

        if not order.driver_id:
            raise serializers.ValidationError(
                f"Order {order.id} has no driver assigned."
            )

        attrs["rider"] = order.driver_id
        return attrs
    



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
            delivery.save()  # ensures ID generation runs
            created_deliveries.append(delivery)

        return created_deliveries



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
        if delivery.rider.user != request.user:
            raise serializers.ValidationError(
                "You can only update deliveries assigned to you."
            )
        
        new_delivery_status = attrs["delivery_status"]
        current_status = delivery.delivery_status

        # 🔥 Prevent rollback
        valid_transitions = {
            "assigned": ["picked_up"],
            "picked_up": ["delivered"],
            "delivered": []
        }

        if new_delivery_status not in valid_transitions[current_status]:
            raise serializers.ValidationError(
                f"Invalid status transition from '{current_status}' to '{new_delivery_status}'."
            )

        attrs["delivery"] = delivery
        return attrs

    def create(self, validated_data):

        with transaction.atomic():

            delivery = Delivery.objects.select_for_update().get(
                pk=validated_data["delivery"].pk
            )

            new_status = validated_data["delivery_status"]
            delivery.delivery_notes = validated_data.get("delivery_notes", "")

            if new_status == "picked_up":
                delivery.picked_up_at = datetime.now()

            if new_status == "delivered":
                delivery.delivered_at = datetime.now()

            delivery.delivery_status = new_status
            delivery.save()

            # 🔥 ORDER UPDATE LOGIC
            order = delivery.package_id.order_id

            # First pickup → in_transit
            if new_status == "picked_up" and order.order_status != Order.Status.IN_TRANSIT:
                order.order_status = Order.Status.IN_TRANSIT
                order.save()

            # If all deliveries delivered → order delivered
            total = Delivery.objects.filter(
                package_id__order_id=order.id
            ).count()

            delivered_count = Delivery.objects.filter(
                package_id__order_id=order.id,
                delivery_status=Delivery.Status.DELIVERED
            ).count()

            if total > 0 and total == delivered_count:
                order.order_status = Order.Status.DELIVERED
                order.save()

                # Driver becomes available
                driver = delivery.rider
                driver.availability_status = True
                driver.save()

        return delivery
