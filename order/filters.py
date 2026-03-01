from django_filters import rest_framework as filters
from .models import Order,Package

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



class PackageFilter(filters.FilterSet):

    # Exact filters
    order_id = filters.CharFilter(field_name="order_id__id")
    fragile = filters.BooleanFilter(field_name="fragile")

    # Range filter
    min_value = filters.NumberFilter(field_name="value", lookup_expr="gte")
    max_value = filters.NumberFilter(field_name="value", lookup_expr="lte")

    # Partial search filters
    receiver_name = filters.CharFilter(field_name="receiver_name", lookup_expr="icontains")
    receiver_phone = filters.CharFilter(field_name="receiver_phone", lookup_expr="icontains")

    class Meta:
        model = Package
        fields = [
            "order_id",
            "fragile",
            "receiver_name",
            "receiver_phone",
        ]