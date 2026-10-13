from django.http import FileResponse
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiTypes
from .models import Delivery, DeliveryEvent
from .serializers import DeliverySerializer
from .lifecycle import resolve_failed


def owned_delivery(user, pk):
    queryset = Delivery.objects.all()
    if not user.is_staff:
        queryset = queryset.filter(Q(package_id__order_id__customer_id=user) | Q(rider__user=user))
    return get_object_or_404(queryset, pk=pk)


class ResolutionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['retry', 'return'])
    reason = serializers.CharField(max_length=350)


class DeliveryResolutionAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(tags=['Delivery'], request=ResolutionSerializer, responses=DeliverySerializer)
    def post(self, request, pk):
        owned_delivery(request.user, pk)
        serializer = ResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        delivery = resolve_failed(pk, request.user, **serializer.validated_data)
        return Response(DeliverySerializer(delivery).data)


class DeliveryEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryEvent
        fields = ['id', 'action', 'reason', 'received_by', 'attempt_number', 'actor', 'created_at']
        read_only_fields = fields


class DeliveryHistoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Delivery'], responses=DeliveryEventSerializer(many=True))
    def get(self, request, pk):
        delivery = owned_delivery(request.user, pk)
        return Response(DeliveryEventSerializer(delivery.events.all(), many=True).data)


class DeliveryProofAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Delivery'], responses={(200, 'image/jpeg'): OpenApiTypes.BINARY})
    def get(self, request, pk):
        from django.http import Http404
        delivery = owned_delivery(request.user, pk)
        if not delivery.proof_photo:
            raise Http404('No delivery photo recorded.')
        try:
            photo = delivery.proof_photo.open('rb')
        except FileNotFoundError:
            raise Http404('Delivery photo is unavailable.')
        response = FileResponse(photo, content_type='image/jpeg', filename=f'{delivery.pk}-proof.jpg')
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
