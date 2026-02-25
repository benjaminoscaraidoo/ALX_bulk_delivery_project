from rest_framework import serializers
from .models import Order, Package
from customer.models import DriverProfile
from delivery.models import Delivery
from django.db import transaction

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
        #request = self.context["request"]
        if not validated_data["receiver_phone"]:
            raise serializers.ValidationError("Receiver Phone number mandatory.")
        

        if not validated_data["receiver_name"]:
            raise serializers.ValidationError("Receiver Name mandatory.")

        return super().create(validated_data)

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
    

class OrderCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Order
        fields = [
            "id",
            "pickup_address",
        ]
        read_only_fields = ["id"]

    def create(self, validated_data):
        request = self.context.get("request")  # get the request
        user = request.user if request else None

        #Only customers can create orders
        if not user or user.role != "customer":
            print("DEBUG: user.role =", getattr(user, "role", None))
            raise serializers.ValidationError("Only customers can create orders.")

        # Force profile completion
        if not getattr(user, "customer_profile", None) or not user.customer_profile.is_complete:
            raise serializers.ValidationError("Complete your profile before placing an order.")

        # Assign available driver
        driver = (
            DriverProfile.objects
            .filter(
                availability_status=True,
                is_complete=True,
                approval_status="approved"
            )
            .exclude(dorders__order_status__in=["pending", "assigned"])  # Prevent driver conflict
            .first()
        )

        order = Order.objects.create(
            customer_id=user,
            driver_id=driver,
            order_status="assigned" if driver else "pending",
            **validated_data
        )

        return order
    

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

        # Assign driver
        order.driver_id = driver
        order.order_status = "assigned"
        order.save()

        return order
    

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

        # Ensure user owns the order
        if order.customer_id != request.user:
            raise serializers.ValidationError(
                "You can only add packages to your own order."
            )
        
        # Ensure delivered orders are not canceled
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

        return order

    


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

        # Ensure user owns the order
        if order.customer_id != request.user:
            raise serializers.ValidationError(
                "You can only add packages to your own order."
            )

        # Prevent modification if already assigned
        #if order.order_status in ["in_transit", "delivered"]:
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
                

        # Ensure user owns the order
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
        """
        We override create() because we're not passing an instance.
        This is technically an UPDATE, but since no instance is passed,
        DRF calls create().
        """

        with transaction.atomic():

            package = Package.objects.select_for_update().get(
                pk=validated_data["package"].pk
            )

            package.receiver_name = validated_data["receiver_name"]
            package.receiver_phone = validated_data["receiver_phone"]

            package.save()


        return package