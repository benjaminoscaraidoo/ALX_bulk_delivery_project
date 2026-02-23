from rest_framework import serializers
from .models import Order, Package
from customer.models import DriverProfile

class PackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Package
        fields = [
            "description",
            "dimensions",
            "fragile",
            "value",
        ]


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

        # Optionally mark driver as unavailable
        #driver.availability_status = False
        #driver.save()

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
        if order.order_status in ["in_transit", "delivered"]:
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