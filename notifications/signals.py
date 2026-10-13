from django.db.models.signals import post_save
from django.dispatch import receiver
from delivery.models import DeliveryEvent, Payment
from order.models import Order
from .services import publish, notify_event


@receiver(post_save, sender=DeliveryEvent)
def delivery_update(sender, instance, created, **kwargs):
    if created:
        notify_event(instance)


@receiver(post_save, sender=Payment)
def payment_update(sender, instance, **kwargs):
    if instance.payment_status == 'paid':
        order = instance.package_id.order_id
        publish(order, f'payment:{instance.pk}:paid', 'Payment confirmed', f'Payment of GHS {instance.amount:.2f} for package {instance.package_id_id} in order {order.pk} has been confirmed.')


@receiver(post_save, sender=Order)
def cancellation_update(sender, instance, **kwargs):
    if instance.order_status == 'cancelled':
        publish(instance, f'order:{instance.pk}:cancelled', 'Order cancelled', f'Order {instance.pk} has been cancelled.')
