from rest_framework import serializers
from .models import Order, Package
from customer.models import DriverProfile
from delivery.models import Delivery
from django.db import transaction
from django.utils import timezone

# Serializer for package 
class PackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Package
        fields = [
            "description",
            "dimensions",
            "fragile",
            "value",
            "receiver_name",
            "receiver_phone",
        ]

    def create(self, validated_data):

        if not validated_data["receiver_phone"]:
            raise serializers.ValidationError("Receiver Phone number mandatory.")
        

        if not validated_data["receiver_name"]:
            raise serializers.ValidationError("Receiver Name mandatory.")

        return super().create(validated_data)


# Serializer for order
class OrderSerializer(serializers.ModelSerializer):
    packages = PackageSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = "__all__"
        read_only_fields = ("customer_id", "order_status", "created_at")

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

        driver = (
            DriverProfile.objects
            .filter(
                availability_status=True,
                is_complete=True,
                approval_status="approved"
            )
            .exclude(dorders__order_status__in=["pending", "assigned"]) 
            .first()
        )

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
        try:
            driver = DriverProfile.objects.get(user__email=value)
        except DriverProfile.DoesNotExist:
            raise serializers.ValidationError("Driver not found.")

        if not driver.is_complete or not driver.is_approved or not driver.availability_status:
            raise serializers.ValidationError("Driver is not available for assignment.")
        return value

    def save(self, **kwargs):
        order = self.context["order"]
        driver = DriverProfile.objects.get(user__email=self.validated_data["driver_email"])

        order.driver_id = driver
        order.order_status = "assigned"
        order.save()

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


        if order.order_status in ["delivered"]:
            raise serializers.ValidationError(
                "Cannot add packages to an active or completed order."
            )

        if not attrs["packages"]:
            raise serializers.ValidationError(
                "At least one package is required."
            )

        return attrs

    def create(self, validated_data):
        order = validated_data["order"]
        packages_data = validated_data["packages"]

        created_packages = []

        for package_data in packages_data:
            pkg = Package.objects.create(order_id=order, **package_data)
            created_packages.append(pkg)

        return created_packages


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

        # Ensure delivery belongs to this rider
        deliveries = Delivery.objects.filter(
            package_id__order_id=order.id
            )

        for delivery in deliveries:
            if delivery.rider.user != request.user:
                raise serializers.ValidationError(
                    "You can only update orders assigned to you."
                )
            
        return attrs  


    def create1(self, validated_data):

        with transaction.atomic():

            order = Order.objects.select_for_update().get(
                pk=validated_data["order"].pk
            )

            # Lock all deliveries belonging to this order
            deliveries = Delivery.objects.select_for_update().filter(
                package_id__order_id=order.id
            )

            if not deliveries.exists():
                raise serializers.ValidationError(
                    "No deliveries found for this order."
                )

            # Update all deliveries
            now = timezone.now()
            deliveries.update(
                delivery_status="picked_up",
                picked_up_at=now
            )

            # Update order status
            order.order_status = Order.Status.IN_TRANSIT
            order.save()

        return order
    
    def create(self, validated_data):

        with transaction.atomic():

            order = Order.objects.select_for_update().get(
                pk=validated_data["order"].pk
            )

            deliveries = Delivery.objects.select_for_update().filter(
                package_id__order_id=order.id
            )

            now = timezone.now()
            new_status = validated_data["status"]

            # Update all deliveries individually (safe for timestamps)
            for delivery in deliveries:

                if new_status == "picked_up":
                    delivery.delivery_status = Delivery.Status.PICKED_UP
                    delivery.picked_up_at = now

                delivery.save()

            # Update Order status
            if new_status == "picked_up":
                order.order_status = Order.Status.IN_TRANSIT

            order.save()

        return order