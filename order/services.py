from django.db.models import Count, Q

from customer.models import DriverProfile


ACTIVE_ORDER_STATUSES = ['pending', 'assigned', 'in_transit']


def eligible_drivers():
    return DriverProfile.objects.filter(
        availability_status=True,
        is_complete=True,
        approval_status='approved',
        user__is_active=True,
        user__role='driver',
    )


def least_busy_driver():
    return eligible_drivers().annotate(
        active_orders=Count('dorders', filter=Q(dorders__order_status__in=ACTIVE_ORDER_STATUSES))
    ).order_by('active_orders', 'pk').first()
