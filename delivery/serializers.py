from rest_framework import serializers
from .models import Delivery, Payment
from order.models import Package

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