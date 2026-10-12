from django.db import transaction

from order.models import Order
from order.services import eligible_drivers, least_busy_driver


def assign_rider_to_delivery(delivery):
    """Use the order's driver, assigning the order first when needed."""
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=delivery.package_id.order_id_id)
        if order.order_status not in [Order.Status.PENDING, Order.Status.ASSIGNED]:
            return None
        if order.driver_id_id:
            rider = eligible_drivers().filter(pk=order.driver_id_id).first()
        else:
            rider = least_busy_driver()
            if rider:
                order.driver_id = rider
                order.order_status = Order.Status.ASSIGNED
                order.save()
        if rider:
            delivery.rider = rider
            delivery.save(update_fields=['rider'])
        return rider
