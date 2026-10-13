from rest_framework import serializers
from .models import Delivery, Payment
from .lifecycle import FAILURE_REASONS
from drf_spectacular.utils import extend_schema_field, OpenApiTypes
from order.models import Package, Order
from django.utils import timezone
from django.db import transaction, IntegrityError

# Serializer for Delivery
class DeliverySerializer(serializers.ModelSerializer):
    proof_photo = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_proof_photo(self, obj):
        return f'/api/v1/delivery/{obj.pk}/proof/' if obj.proof_photo else None

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

        if order.order_status not in [Order.Status.PENDING, Order.Status.ASSIGNED]:
            raise serializers.ValidationError("Deliveries can only be created before pickup on uncancelled orders.")

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
        items = validated_data["deliveries"]
        ids = [item["package_id"].pk for item in items]
        if not ids or len(ids) != len(set(ids)):
            raise serializers.ValidationError("Select at least one package, with no duplicates.")
        try:
            with transaction.atomic():
                order_ids = sorted({item["package_id"].order_id_id for item in items})
                orders = {order.pk: order for order in Order.objects.select_for_update().filter(pk__in=order_ids).order_by('pk')}
                packages = {package.pk: package for package in Package.objects.select_for_update().filter(pk__in=ids).order_by('pk')}
                created = []
                for item in items:
                    package = packages.get(item["package_id"].pk)
                    if not package or package.order_id_id not in orders:
                        raise serializers.ValidationError("Package no longer exists. Refresh and try again.")
                    package.order_id = orders[package.order_id_id]
                    fresh = DeliveryItemSerializer(context=self.context).validate({
                        "package_id": package, "address": item.get("address", "")
                    })
                    created.append(Delivery.objects.create(package_id=package, rider=fresh['rider'], address=fresh.get('address', '')))
                return created
        except IntegrityError:
            raise serializers.ValidationError("A delivery already exists for one of these packages. Refresh and try again.")


@extend_schema_field(OpenApiTypes.BINARY)
class ProofPhotoField(serializers.FileField):
    pass


# Serializer for Delivery status update by assigned driver/riders
class DriverDeliveryUpdateSerializer(serializers.Serializer):
    package_id = serializers.PrimaryKeyRelatedField(queryset=Package.objects.all(), source='package', write_only=True)
    delivery_status = serializers.ChoiceField(choices=['picked_up', 'delivered', 'failed', 'returned'])
    delivery_notes = serializers.CharField(max_length=300, required=False, allow_blank=True)
    received_by = serializers.CharField(max_length=150, required=False, allow_blank=True)
    failure_reason = serializers.ChoiceField(choices=FAILURE_REASONS, required=False)
    proof_photo = ProofPhotoField(required=False)
    starting_address = serializers.CharField(max_length=350, required=False, allow_blank=True)

    def validate_proof_photo(self, value):
        from .proof import clean_photo
        return clean_photo(value)

    def validate(self, attrs):
        from .lifecycle import validate_driver_action
        try:
            delivery = attrs['package'].deliveries
        except Delivery.DoesNotExist:
            raise serializers.ValidationError('Delivery not found.')
        validate_driver_action(delivery, self.context['request'].user, attrs)
        attrs['delivery'] = delivery
        return attrs

    def create(self, validated_data):
        from .lifecycle import driver_action
        return driver_action(validated_data['delivery'].pk, self.context['request'].user, validated_data)
