from django.contrib import admin
from django.utils.html import format_html
from .models import Delivery, Payment, DeliveryEvent
# Register your models here.
@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ("id","package_id", "delivery_status", "assigned_at")
    list_filter = ("delivery_status",)
    search_fields = ("package_id__order_id__id", "rider__user__email")
    readonly_fields = tuple(field.name for field in Delivery._meta.fields if field.name != 'proof_photo') + ('delivery_photo',)
    exclude = ('proof_photo',)

    def delivery_photo(self, obj):
        if not obj.proof_photo:
            return 'No photo recorded'
        return format_html('<a href="/api/v1/delivery/{}/proof/">View delivery photo</a>', obj.pk)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("package_id", "amount", "payment_method", "payment_status", "paid_at")
    list_filter = ("payment_method", "payment_status")
    search_fields = ("transaction_reference",)
    readonly_fields = ("package_id", "payment_method", "amount", "payment_status", "paid_at", "confirmed_by", "transaction_reference", "transaction_recorded_by", "transaction_recorded_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DeliveryEvent)
class DeliveryEventAdmin(admin.ModelAdmin):
    list_display = ('delivery', 'action', 'attempt_number', 'actor', 'created_at')
    readonly_fields = tuple(field.name for field in DeliveryEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
