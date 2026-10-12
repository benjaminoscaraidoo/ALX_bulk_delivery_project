from rest_framework import serializers
from .models import Order, Package
from customer.models import DriverProfile
from delivery.models import Delivery
from .services import eligible_drivers, least_busy_driver
from django.db import transaction
from django.utils import timezone

# Serializer for package 
class PackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Package
        fields = [
            "id",
            "delivery_address",
            "outside_accra",
            "delivery_area",
            "description",
            "dimensions",
            "fragile",
            "value",
            "receiver_name",
            "receiver_phone",
        ]

        read_only_fields = ["id"]

    def validate(self, attrs):
        if attrs.get("outside_accra"):
            area = attrs.get("delivery_area")
            if not area or not area.enabled:
                raise serializers.ValidationError("Select an enabled outside-Accra area.")
        elif attrs.get("delivery_area"):
            raise serializers.ValidationError("Delivery area is only for outside-Accra packages.")
        return attrs

    def create(self, validated_data):

        if not validated_data["receiver_phone"]:
            raise serializers.ValidationError("Receiver Phone number mandatory.")
        

        if not validated_data["receiver_name"]:
            raise serializers.ValidationError("Receiver Name mandatory.")

        return super().create(validated_data)


# Serializer for order
class OrderSerializer(serializers.ModelSerializer):
    pricing_complete = serializers.SerializerMethodField()

    def get_pricing_complete(self, obj) -> bool:
        return obj.packages.exists() and not obj.packages.filter(quote__isnull=True).exists()

    packages = PackageSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = "__all__"
        read_only_fields = ("customer_id", "order_status", "created_at", "total_price")

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["customer_id"] = request.user
        return super().create(validated_data)
    

# Serializer for order creation
class OrderCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Order
        fields = [
            "id",
            "pickup_address",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        request = self.context.get("request")  
        user = request.user if request else None

        if not user or user.role != "customer":
            print("DEBUG: user.role =", getattr(user, "role", None))
            raise serializers.ValidationError("Only customers can create orders.")

        if not getattr(user, "customer_profile", None) or not user.customer_profile.is_complete:
            raise serializers.ValidationError("Complete your profile before placing an order.")

        driver = least_busy_driver()

        order = Order.objects.create(
            customer_id=user,
            driver_id=driver,
            order_status="assigned" if driver else "pending",
            **validated_data
        )

        return order
    

# Serializer for manually assigning order to a driver/rider
class OrderAssignSerializer(serializers.Serializer):
    driver_email = serializers.EmailField(required=True)

    def validate_driver_email(self, value):
        if not eligible_drivers().filter(user__email=value).exists():
            raise serializers.ValidationError("Driver is not eligible or available for assignment.")
        return value

    def validate(self, attrs):
        order = self.context["order"]
        if order.order_status not in [Order.Status.PENDING, Order.Status.ASSIGNED]:
            raise serializers.ValidationError("Only pending or assigned orders can be reassigned.")
        if Delivery.objects.filter(package_id__order_id=order).exclude(
            delivery_status=Delivery.Status.ASSIGNED
        ).exists():
            raise serializers.ValidationError("Cannot reassign an order after deliveries have started.")
        return attrs

    def save(self, **kwargs):
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=self.context["order"].pk)
            self.context["order"] = order
            self.validate(self.validated_data)
            try:
                driver = eligible_drivers().select_for_update().get(
                    user__email=self.validated_data["driver_email"]
                )
            except DriverProfile.DoesNotExist:
                raise serializers.ValidationError("Driver is not eligible or available for assignment.")
            order.driver_id = driver
            order.order_status = Order.Status.ASSIGNED
            order.save()
            Delivery.objects.filter(package_id__order_id=order).update(rider=driver)
        return order
    

# Serializer for cancelling orders
class OrderCancelSerializer(serializers.Serializer):
    cancel_reason = serializers.CharField(required=True)
    order_id = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(),
        source="order",
        write_only=True,
        required=True
    )

    def validate(self, attrs):
        order = attrs.get("order")
        request = self.context["request"]

        if order.customer_id != request.user:
            raise serializers.ValidationError(
                "You can only add packages to your own order."
            )
        
        if order.order_status in ["delivered"]:
            raise serializers.ValidationError(
                "Cannot cancel delivered order."
            )
        

        delivered_count = Delivery.objects.filter(
                package_id__order_id=order.id,
                delivery_status=Delivery.Status.DELIVERED
            ).count()

        if delivered_count > 0:
            raise serializers.ValidationError(
                "Cannot cancel an order with packages delivered."
            )
    
        return attrs  


    def create(self, validated_data):

        with transaction.atomic():
            order = Order.objects.select_for_update().get(
                pk=validated_data["order"].pk
            )
            self.validate({**validated_data, "order": order})
            order.order_status = "cancelled"
            order.cancel_reason = validated_data["cancel_reason"]
            order.save()

            Delivery.objects.filter(
                package_id__order_id=order.id
                ).exclude(
                    delivery_status=Delivery.Status.DELIVERED
                ).update(
                    delivery_status=Delivery.Status.CANCELLED,
                    delivered_at=None
                )
            
        return order
    

# Serializer for creating packages
class CreatePackagesSerializer(serializers.Serializer):
    order_id = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(),
        source="order",
        write_only=True
    )
    packages = PackageSerializer(many=True)

    def validate(self, attrs):
        order = attrs["order"]
        request = self.context["request"]


        if order.customer_id != request.user:
            raise serializers.ValidationError(
                "You can only add packages to your own order."
            )


        if order.order_status not in [Order.Status.PENDING, Order.Status.ASSIGNED]:
            raise serializers.ValidationError(
                "Packages can only be added to pending or assigned orders."
            )

        if not attrs["packages"]:
            raise serializers.ValidationError(
                "At least one package is required."
            )

        return attrs

    def create(self, validated_data):
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=validated_data["order"].pk)
            self.validate({**validated_data, "order": order})
            return [
                Package.objects.create(order_id=order, **package_data)
                for package_data in validated_data["packages"]
            ]


# Serialier for package information update
class PackageDetailsUpdateSerializer(serializers.Serializer):

    package_id = serializers.PrimaryKeyRelatedField(
        queryset=Package.objects.all(),
        source="package",
        write_only=True
    )

    receiver_name = serializers.CharField(required=True)
    receiver_phone = serializers.CharField(required=True)

    def validate(self, attrs):
        package = attrs.get("package")
        request = self.context["request"]

        try:
            delivery = package.deliveries
        except Delivery.DoesNotExist:
            raise serializers.ValidationError("Delivery not found.")
        
        try:
            order = package.order_id
        except Order.DoesNotExist:
            raise serializers.ValidationError("Order not found.")
                

        if order.customer_id != request.user:
            raise serializers.ValidationError(
                "You can only update packages to your own order."
            )
        

        if delivery.delivery_status in ["delivered"]:
            raise serializers.ValidationError(
                "You cannot update receiver details for delivered items."
            )
        
        attrs["package"] = package
        return attrs
    

    def create(self, validated_data):

        with transaction.atomic():

            package = Package.objects.select_for_update().get(
                pk=validated_data["package"].pk
            )

            package.receiver_name = validated_data["receiver_name"]
            package.receiver_phone = validated_data["receiver_phone"]

            package.save()


        return package
    




# Serializer for cancelling orders
class OrderUpdateSerializer(serializers.Serializer):
    status = serializers.CharField(required=True)
    order_id = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(),
        source="order",
        write_only=True,
        required=True
    )

    def validate(self, attrs):
        order = attrs.get("order")
        request = self.context["request"]
        new_status = attrs["status"]

        if new_status != "picked_up":
            raise serializers.ValidationError(
                "Only 'picked_up' status is allowed for this endpoint."
            )

        # Ensure order is not already in transit or delivered
        if order.order_status in [
            Order.Status.IN_TRANSIT,
            Order.Status.DELIVERED,
            Order.Status.CANCELLED
        ]:
            raise serializers.ValidationError(
                f"Order cannot be moved to picked_up from '{order.order_status}'."
            )

        if order.order_status != Order.Status.ASSIGNED:
            raise serializers.ValidationError("Only assigned orders can be picked up.")
        if not order.driver_id or order.driver_id.user_id != request.user.pk:
            raise serializers.ValidationError("You can only update orders assigned to you.")

        deliveries = Delivery.objects.filter(package_id__order_id=order.pk)
        if not deliveries.exists():
            raise serializers.ValidationError("No deliveries found for this order.")
        if order.packages.count() != deliveries.count():
            raise serializers.ValidationError("Every package must have a delivery before pickup.")
        for delivery in deliveries:
            if delivery.rider_id != order.driver_id_id:
                raise serializers.ValidationError("All deliveries must belong to the assigned driver.")
            if delivery.delivery_status != Delivery.Status.ASSIGNED:
                raise serializers.ValidationError("All deliveries must be assigned before pickup.")
        return attrs

    def create(self, validated_data):
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=validated_data["order"].pk)
            self.validate({**validated_data, "order": order})
            deliveries = Delivery.objects.select_for_update().filter(package_id__order_id=order.pk)
            deliveries.update(delivery_status=Delivery.Status.PICKED_UP, picked_up_at=timezone.now())
            order.order_status = Order.Status.IN_TRANSIT
            order.save()
        return order
