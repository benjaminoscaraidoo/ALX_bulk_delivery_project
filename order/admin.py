from django.contrib import admin
from .models import Order, Package, DistanceTariff, DeliveryArea, DeliveryQuote


class PackageInline(admin.TabularInline):
    model = Package
    extra = 0

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in Package._meta.fields] if obj else []


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer_id", "driver_id", "order_status", "delivery_date", "total_price", "created_at")
    list_filter = ("order_status", "delivery_date")
    search_fields = ("id", "customer_id__email")
    readonly_fields = ("total_price",)
    inlines = [PackageInline]

    def get_readonly_fields(self, request, obj=None):
        if obj and DeliveryQuote.objects.filter(package__order_id=obj).exists():
            return ("total_price", "pickup_address")
        return ("total_price",)


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ("id", "order_id", "dimensions", "fragile")
    search_fields = ("order_id__id",)


    def get_readonly_fields(self, request, obj=None):
        if obj and DeliveryQuote.objects.filter(package=obj).exists():
            return ("order_id", "delivery_address", "outside_accra", "delivery_area")
        return ()


@admin.register(DistanceTariff)
class DistanceTariffAdmin(admin.ModelAdmin):
    list_display = ['upper_km', 'charge', 'enabled']


@admin.register(DeliveryArea)
class DeliveryAreaAdmin(admin.ModelAdmin):
    list_display = ['name', 'charge', 'enabled']


@admin.register(DeliveryQuote)
class DeliveryQuoteAdmin(admin.ModelAdmin):
    list_display = ['package', 'amount', 'distance_meters', 'created_at']
    readonly_fields = [field.name for field in DeliveryQuote._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
