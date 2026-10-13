from .models import Notification


def inbox(request):
    if request.user.is_authenticated and request.user.role == 'customer':
        return {'notification_unread_count': Notification.objects.filter(customer=request.user, read_at__isnull=True).count()}
    return {'notification_unread_count': 0}
