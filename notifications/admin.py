from django.contrib import admin
from .models import Notification, NotificationSend


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['customer', 'order', 'title', 'created_at', 'read_at']
    readonly_fields = tuple(field.name for field in Notification._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NotificationSend)
class NotificationSendAdmin(admin.ModelAdmin):
    list_display = ['notification', 'channel', 'status', 'attempts', 'sent_at', 'last_error']
    list_filter = ['channel', 'status']
    readonly_fields = tuple(field.name for field in NotificationSend._meta.fields)
    actions = ['retry_selected']

    @admin.action(description='Retry selected pending or failed notifications')
    def retry_selected(self, request, queryset):
        from .services import dispatch
        sent = 0
        for pk in queryset.filter(status__in=['pending', 'failed']).values_list('pk', flat=True)[:100]:
            try:
                sent += int(dispatch(pk, retry_now=True))
            except Exception:
                continue
        self.message_user(request, f'Sent {sent} queued notifications. Check each remaining job for its status.')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
