from django_filters import rest_framework as filters
from .models import Delivery

class DeliveryFilter(filters.FilterSet):
    # Date Range Filters
    start_delivered_date = filters.DateFilter(field_name="delivered_at", lookup_expr='gte')
    end_delivered_date = filters.DateFilter(field_name="delivered_at", lookup_expr='lte')

    start_pickup_date = filters.DateFilter(field_name="picked_up_at", lookup_expr='gte')
    end_pickup_date = filters.DateFilter(field_name="picked_up_at", lookup_expr='lte')
    
    # Exact Field Filters
    delivery_status = filters.CharFilter(field_name="delivery_status")
    driver = filters.NumberFilter(field_name="rider")

    class Meta:
        model = Delivery
        fields = ['delivery_status', 'driver', 'start_delivered_date', 'end_delivered_date', 'start_pickup_date', 'end_pickup_date']