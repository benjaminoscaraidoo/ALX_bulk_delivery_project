from django.db import transaction, IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, generics
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from order.models import Package, Order, DeliveryQuote
from .models import Payment, Delivery


class PaymentReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'package_id', 'amount', 'payment_method', 'payment_status', 'transaction_reference', 'paid_at', 'confirmed_by']
        read_only_fields = fields


class PaymentCreateSerializer(serializers.Serializer):
    package_id = serializers.PrimaryKeyRelatedField(queryset=Package.objects.all())
    payment_method = serializers.ChoiceField(choices=Payment.Method.choices)


class PaymentCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=PaymentCreateSerializer, responses={201: PaymentReadSerializer})
    def post(self, request):
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        package = serializer.validated_data['package_id']
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=package.order_id_id)
            if order.customer_id_id != request.user.pk:
                raise PermissionDenied('You can only create payments for your own packages.')
            if order.order_status == Order.Status.CANCELLED:
                raise ValidationError('Cannot pay for a cancelled order.')
            quote = DeliveryQuote.objects.filter(package=package).first()
            if not quote:
                raise ValidationError('A confirmed delivery quote is required.')
            if Payment.objects.filter(package_id=package).exists():
                raise ValidationError('A payment already exists for this package.')
            payment = Payment.objects.create(package_id=package, amount=quote.amount,
                payment_method=serializer.validated_data['payment_method'])
        return Response(PaymentReadSerializer(payment).data, status=201)


class PaymentListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PaymentReadSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Payment.objects.none()
        user = self.request.user
        if user.is_staff:
            return Payment.objects.all().order_by('id')
        if user.role == 'driver':
            return Payment.objects.filter(package_id__deliveries__rider__user=user).order_by('id')
        return Payment.objects.filter(package_id__order_id__customer_id=user).order_by('id')


class PaymentConfirmSerializer(serializers.Serializer):
    transaction_reference = serializers.CharField(max_length=150, required=False, allow_blank=True)


class PaymentConfirmAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=PaymentConfirmSerializer, responses={200: PaymentReadSerializer})
    def post(self, request, pk):
        serializer = PaymentConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        initial = get_object_or_404(Payment, pk=pk)
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=initial.package_id.order_id_id)
            payment = Payment.objects.select_for_update().get(pk=pk)
            if payment.payment_method == Payment.Method.CASH:
                if request.user.role != 'driver' or not Delivery.objects.filter(
                    package_id=payment.package_id, rider__user=request.user
                ).exists():
                    raise PermissionDenied('Only the assigned driver can confirm cash.')
            elif not request.user.is_staff:
                raise PermissionDenied('Only administrators can confirm mobile money.')
            if order.order_status == Order.Status.CANCELLED:
                raise ValidationError('Cannot confirm payment for a cancelled order.')
            if payment.payment_status != Payment.Status.PENDING:
                raise ValidationError('Only pending payments can be confirmed.')
            reference = serializer.validated_data.get('transaction_reference', '').strip()
            if payment.payment_method == Payment.Method.MOBILE_MONEY and not reference:
                raise ValidationError('Mobile money transaction reference is required.')
            if reference and Payment.objects.filter(payment_status=Payment.Status.PAID, transaction_reference=reference).exists():
                raise ValidationError('Transaction reference has already been used.')
            payment.payment_status = Payment.Status.PAID
            payment.paid_at = timezone.localdate()
            payment.confirmed_by = request.user
            payment.transaction_reference = reference
            try:
                with transaction.atomic():
                    payment.save()
            except IntegrityError:
                raise ValidationError("Transaction reference has already been used.")
        return Response(PaymentReadSerializer(payment).data)
