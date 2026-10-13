from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Delivery
from .services import assign_rider_to_delivery


@receiver(post_save, sender=Delivery)
def auto_assign_rider(sender, instance, created, **kwargs):
    if kwargs.get('raw'):
        return
    if created and instance.rider is None:
        assign_rider_to_delivery(instance)
    if created and instance.rider_id:
        from .routing import schedule_route
        schedule_route(instance.rider_id)
