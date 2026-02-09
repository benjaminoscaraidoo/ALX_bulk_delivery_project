from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from .models import User, CustomerProfile, DriverProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatically create profile based on user role
    """
    if not created:
        return

    if instance.role == User.Role.CUSTOMER:
        CustomerProfile.objects.get_or_create(user=instance)

    elif instance.role == User.Role.DRIVER:
        DriverProfile.objects.get_or_create(user=instance)
