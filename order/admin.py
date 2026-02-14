from django.contrib import admin
from .models import Order, Package


class PackageInline(admin.TabularInline):
    model = Package
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer_id", "driver_id", "order_status", "delivery_date", "total_price", "created_at")
    list_filter = ("order_status", "delivery_date")
    search_fields = ("id", "customer__email")
    inlines = [PackageInline]


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ("id", "order_id", "dimensions", "fragile")
    search_fields = ("order__id",)
