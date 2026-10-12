from rest_framework import serializers, generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
from .models import Package, DeliveryArea, DeliveryQuote
from .pricing import create_quote


class AreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryArea
        fields = ['id', 'name', 'charge']


class AreaListAPIView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    queryset = DeliveryArea.objects.filter(enabled=True).order_by('name')
    serializer_class = AreaSerializer


class QuoteRequestSerializer(serializers.Serializer):
    package_id = serializers.PrimaryKeyRelatedField(queryset=Package.objects.all())
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)
    reason = serializers.CharField(max_length=350, required=False, allow_blank=True)


class QuoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryQuote
        fields = ['id', 'package', 'amount', 'distance_meters', 'pickup_address', 'delivery_address', 'outside_accra', 'area_name', 'reason', 'created_at']


class PackageQuoteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=QuoteRequestSerializer, responses={200: QuoteSerializer})
    def post(self, request):
        serializer = QuoteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        quote, distance = create_quote(data['package_id'].pk, request.user, data.get('amount'), data.get('reason', ''))
        if quote is None:
            return Response({'quote_required': True, 'distance_meters': distance, 'detail': 'Administrator quote required.'})
        return Response(QuoteSerializer(quote).data)
