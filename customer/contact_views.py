from django.db import IntegrityError
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from drf_spectacular.utils import extend_schema
from .models import CustomUser, CustomerProfile
from .services import send_otp, verify_otp, confirm_account_token
from .sms import normalize_phone
from .throttles import OTPRegisterThrottle, OTPVerifyThrottle


class ContactRequestSerializer(serializers.Serializer):
    delivery_channel = serializers.ChoiceField(choices=['email', 'sms'])
    value = serializers.CharField(max_length=254)

    def validate(self, attrs):
        value = attrs['value']
        if attrs['delivery_channel'] == 'sms':
            attrs['value'] = normalize_phone(value)
        else:
            attrs['value'] = serializers.EmailField().run_validation(value).lower()
        return attrs


class ContactVerifySerializer(serializers.Serializer):
    delivery_channel = serializers.ChoiceField(choices=['email', 'sms'])
    otp = serializers.CharField(max_length=6)


class ContactRequestAPIView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [OTPRegisterThrottle]

    @extend_schema(request=ContactRequestSerializer, responses={200: None})
    def post(self, request):
        serializer = ContactRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        channel, value = serializer.validated_data['delivery_channel'], serializer.validated_data['value']
        lookup = {'phone_number': value} if channel == 'sms' else {'email__iexact': value}
        if CustomUser.objects.filter(**lookup).exclude(pk=request.user.pk).exists():
            raise ValidationError('This contact is already linked to another account.')
        send_otp(request.user, 'contact_phone' if channel == 'sms' else 'contact_email', channel, value)
        return Response({'message': 'Verification code sent.'})


class ContactVerifyAPIView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [OTPVerifyThrottle]

    @extend_schema(request=ContactVerifySerializer, responses={200: None})
    def post(self, request):
        serializer = ContactVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        channel = data['delivery_channel']
        purpose = 'contact_phone' if channel == 'sms' else 'contact_email'
        token = verify_otp(None, data['otp'], purpose, channel, user_id=request.user.pk)
        def link(user):
            user.save(update_fields=['email', 'email_verified', 'phone_number', 'phone_verified'])
            if user.role == 'customer':
                profile = CustomerProfile.objects.get(user=user)
                profile.is_complete = bool(profile.customer_name and profile.address.strip() and user.phone_number and user.phone_verified)
                profile.save(update_fields=['is_complete'])
        try:
            confirm_account_token(token, purpose, link)
        except IntegrityError:
            raise ValidationError('This contact was linked to another account. Request a new code.')
        return Response({'message': 'Contact verified and linked to your account.'})
