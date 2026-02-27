from django_filters import rest_framework as filters
from .models import Order

class OrderFilter(filters.FilterSet):
    # Date Range Filters
    start_created_date = filters.DateFilter(field_name="created_at", lookup_expr='gte')
    end_created_date = filters.DateFilter(field_name="created_at", lookup_expr='lte')
    
    # Exact Field Filters
    orderstatus = filters.CharFilter(field_name="order_status")
    customer = filters.NumberFilter(field_name="customer_id")

    class Meta:
        model = Order
        fields = ['orderstatus', 'customer', 'start_created_date', 'end_created_date']