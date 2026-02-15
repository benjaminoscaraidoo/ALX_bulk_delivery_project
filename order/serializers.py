from rest_framework import serializers
from .models import Order, Package


class PackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Package
        fields = "__all__"
        read_only_fields = ("order",)


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
