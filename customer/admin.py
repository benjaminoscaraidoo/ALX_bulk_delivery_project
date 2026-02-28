from django.contrib import admin
from .models import CustomUser, CustomerProfile, DriverProfile,EmailOTP


@admin.register(CustomUser)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "phone_number", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "phone_number")
    ordering = ("-created_at",)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "customer_name", "date_modified")
    search_fields = ("user__email", "customer_name")


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "vehicle_type", "vehicle_number", "availability_status")
    list_filter = ("availability_status",)
    search_fields = ("user__email", "vehicle_number")


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "is_verified")
    search_fields = ("user__email","created_at")
