from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, generics
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'order', 'title', 'body', 'created_at', 'read_at']
        read_only_fields = fields


class NotificationListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Notification.objects.none()
        return Notification.objects.filter(customer=self.request.user)


class NotificationReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Notifications'], request=None, responses=NotificationSerializer)
    def post(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, customer=request.user)
        Notification.objects.filter(pk=pk, read_at__isnull=True).update(read_at=timezone.now())
        notification.refresh_from_db()
        return Response(NotificationSerializer(notification).data)
