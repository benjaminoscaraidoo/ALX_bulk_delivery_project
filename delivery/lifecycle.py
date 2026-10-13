from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from order.models import Order
from .models import Delivery, DeliveryEvent
from .routing import schedule_route

FAILURE_REASONS = [('receiver_unavailable', 'Receiver unavailable'), ('wrong_address', 'Address could not be located'), ('receiver_refused', 'Receiver refused package'), ('access_issue', 'Could not access location'), ('other', 'Other')]
TERMINAL_ORDERS = ['cancelled', 'delivered', 'returned', 'completed_returns']


def validate_driver_action(delivery, user, data):
    if not delivery.rider_id or delivery.rider.user_id != user.pk:
        raise ValidationError('You can only update deliveries assigned to you.')
    if delivery.package_id.order_id.order_status in TERMINAL_ORDERS:
        raise ValidationError('Cannot update deliveries for a cancelled or completed order.')
    transitions = {'assigned': ['picked_up'], 'picked_up': ['delivered', 'failed'], 'returning': ['returned']}
    status = data['delivery_status']
    if status not in transitions.get(delivery.delivery_status, []):
        raise ValidationError(f"Invalid status transition from '{delivery.delivery_status}' to '{status}'.")
    if status in ['delivered', 'returned'] and not data.get('received_by', '').strip():
        raise ValidationError({'received_by': 'Enter the name of the person who received the package.'})
    if status == 'failed' and not data.get('failure_reason'):
        raise ValidationError({'failure_reason': 'Select the reason the attempt failed.'})
    if status == 'failed' and data.get('failure_reason') == 'other' and not data.get('delivery_notes', '').strip():
        raise ValidationError({'delivery_notes': 'Describe why the attempt failed.'})
    if data.get('proof_photo') and status != 'delivered':
        raise ValidationError('Delivery photos can only be recorded when completing delivery.')


def sync_order(order):
    statuses = list(Delivery.objects.filter(package_id__order_id=order).values_list('delivery_status', flat=True))
    if len(statuses) == order.packages.count() and statuses and all(s in ['delivered', 'returned'] for s in statuses):
        order.order_status = 'delivered' if all(s == 'delivered' for s in statuses) else ('returned' if all(s == 'returned' for s in statuses) else 'completed_returns')
    else:
        order.order_status = 'in_transit'
    order.save(update_fields=['order_status'])


def driver_action(delivery_id, user, data):
    saved_photo = None
    try:
        with transaction.atomic():
            order_id = Delivery.objects.values_list('package_id__order_id_id', flat=True).get(pk=delivery_id)
            order = Order.objects.select_for_update().get(pk=order_id)
            delivery = Delivery.objects.select_for_update().select_related('rider', 'package_id__order_id').get(pk=delivery_id)
            delivery.package_id.order_id = order
            validate_driver_action(delivery, user, data)
            status = data['delivery_status']
            delivery.delivery_notes = data.get('delivery_notes', '')
            if status == 'picked_up':
                delivery.picked_up_at = timezone.now()
            if status in ['failed', 'delivered']:
                delivery.attempt_count += 1
            if status == 'failed':
                delivery.failure_reason = data['failure_reason']
            if status in ['delivered', 'returned']:
                delivery.received_by = data['received_by'].strip()
                if status == 'delivered':
                    delivery.delivered_at = timezone.now()
                else:
                    delivery.returned_at = timezone.now()
            if data.get('proof_photo'):
                delivery.proof_photo.save(data['proof_photo'].name, data['proof_photo'], save=False)
                saved_photo = delivery.proof_photo.name
            delivery.delivery_status = status
            delivery.save()
            DeliveryEvent.objects.create(delivery=delivery, action=status, reason=(dict(FAILURE_REASONS).get(data.get('failure_reason'), '') + ': ' if status == 'failed' else '') + data.get('delivery_notes', ''), received_by=delivery.received_by if status in ['delivered', 'returned'] else '', attempt_number=delivery.attempt_count, actor=user)
            sync_order(order)
            if status == 'failed':
                schedule_route(delivery.rider_id)
        return delivery
    except Exception:
        if saved_photo:
            Delivery._meta.get_field('proof_photo').storage.delete(saved_photo)
        raise


def resolve_failed(delivery_id, user, action, reason):
    with transaction.atomic():
        order_id = Delivery.objects.values_list('package_id__order_id_id', flat=True).get(pk=delivery_id)
        order = Order.objects.select_for_update().get(pk=order_id)
        delivery = Delivery.objects.select_for_update().get(pk=delivery_id)
        if not user.is_staff:
            raise ValidationError('Only administrators can authorize retries or returns.')
        if order.order_status in TERMINAL_ORDERS or delivery.delivery_status != 'failed':
            raise ValidationError('Only failed deliveries on active orders can be resolved.')
        if not delivery.rider_id:
            raise ValidationError('Assign a driver before resolving this delivery.')
        delivery.delivery_status = 'picked_up' if action == 'retry' else 'returning'
        delivery.save(update_fields=['delivery_status'])
        DeliveryEvent.objects.create(delivery=delivery, action=action, reason=reason, attempt_number=delivery.attempt_count, actor=user)
        schedule_route(delivery.rider_id)
        return delivery
