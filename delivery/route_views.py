from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from customer.permissions import IsDriver
from .routing import current_route, optimize_route


class RouteRequestSerializer(serializers.Serializer):
    starting_address = serializers.CharField(max_length=350, required=False, allow_blank=True)


class RouteStopSerializer(serializers.Serializer):
    key = serializers.CharField()
    kind = serializers.CharField()
    address = serializers.CharField()
    order_id = serializers.CharField()
    package_id = serializers.CharField(required=False)
    delivery_id = serializers.CharField(required=False)
    recipient = serializers.CharField(required=False)
    requires = serializers.CharField(allow_null=True)


class RouteSerializer(serializers.Serializer):
    stops = RouteStopSerializer(many=True)
    starting_address = serializers.CharField(allow_blank=True)
    waiting_orders = serializers.IntegerField()
    needs_refresh = serializers.BooleanField()
    generated_at = serializers.DateTimeField(allow_null=True)
    distance_meters = serializers.IntegerField(allow_null=True)
    duration_seconds = serializers.IntegerField(allow_null=True)


class DriverRouteAPIView(APIView):
    permission_classes = [IsAuthenticated, IsDriver]

    @extend_schema(tags=['Delivery'], responses=RouteSerializer)
    def get(self, request):
        return Response(current_route(request.user.driverprofile.pk))


class DriverRouteOptimizeAPIView(APIView):
    permission_classes = [IsAuthenticated, IsDriver]

    @extend_schema(tags=['Delivery'], request=RouteRequestSerializer, responses=RouteSerializer)
    def post(self, request):
        serializer = RouteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(optimize_route(request.user.driverprofile.pk, serializer.validated_data.get('starting_address', '')))
