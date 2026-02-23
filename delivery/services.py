from customer.models import DriverProfile
from .models import Delivery
from django.db.models import Count


def assign_rider_to_delivery(delivery):
    """
    Assign the least busy available rider to a delivery.
    """

    rider = (
        DriverProfile.objects
        .filter(is_available=True)
        .annotate(active_jobs=Count("assigned_deliveries"))
        .order_by("active_jobs")
        .first()
    )

    if rider:
        delivery.rider = rider
        delivery.status = "Assigned"
        delivery.save()

    return rider