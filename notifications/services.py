import logging
from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from customer.sms import check_sms_configuration, SMSUnavailable, send_sms
from .models import Notification, NotificationSend

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 5


def publish(order, key, title, body):
    """Create the inbox item and outbound jobs in the caller's transaction."""
    with transaction.atomic():
        notification, created = Notification.objects.get_or_create(event_key=key, defaults=dict(customer_id=order.customer_id_id, order=order, title=title, body=body))
        if not created:
            return notification
        customer = order.customer_id
        for channel, destination, verified in [('email', customer.email, customer.email_verified), ('sms', customer.phone_number, customer.phone_verified)]:
            if destination and verified:
                job = NotificationSend.objects.create(notification=notification, channel=channel, destination=destination)
                if settings.NOTIFICATION_SEND_IMMEDIATELY:
                    transaction.on_commit(lambda pk=job.pk: safely_dispatch(pk))
        return notification


def safely_dispatch(pk):
    try:
        dispatch(pk)
    except Exception:
        # Notification infrastructure must never fail an already committed operation.
        logger.warning('Notification job %s needs retry.', pk)


def dispatch(pk, retry_now=False):
    now = timezone.now()
    with transaction.atomic():
        job = NotificationSend.objects.select_for_update(of=('self',)).select_related('notification__customer').filter(pk=pk).first()
        if not job or job.status in ['sent', 'skipped'] or job.attempts >= MAX_ATTEMPTS:
            return False
        if job.status == 'sending' and job.claimed_at and job.claimed_at > now - timedelta(minutes=15):
            return False
        if not retry_now and job.next_attempt_at > now:
            return False
        user = job.notification.customer
        current = user.email if job.channel == 'email' else user.phone_number
        verified = user.email_verified if job.channel == 'email' else user.phone_verified
        if not user.is_active or not verified or current != job.destination:
            job.status = 'skipped'
            job.last_error = 'Contact is no longer verified or account is inactive.'
            job.save(update_fields=['status', 'last_error'])
            return False
        configured = bool(settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD) if settings.EMAIL_BACKEND.endswith('smtp.EmailBackend') else True
        if job.channel == 'sms':
            try:
                check_sms_configuration()
                configured = True
            except SMSUnavailable:
                configured = False
        if not configured:
            job.status = 'pending'
            job.last_error = f'{job.channel.upper()} configuration required.'
            job.next_attempt_at = now + timedelta(minutes=15)
            job.save(update_fields=['status', 'last_error', 'next_attempt_at'])
            return False
        job.status = 'sending'
        job.claimed_at = now
        job.attempts += 1
        job.save(update_fields=['status', 'claimed_at', 'attempts'])
        notification = job.notification
        channel, destination = job.channel, job.destination
    # Network requests run outside the row-lock transaction.
    try:
        body = f'OY Delivery Services: {notification.body}'
        if settings.PUBLIC_APP_URL:
            body += f'\nView your order: {settings.PUBLIC_APP_URL.rstrip("/")}/orders/{notification.order_id}/'
        if channel == 'email':
            if send_mail('OY Delivery Services — ' + notification.title, body, settings.EMAIL_HOST_USER or settings.DEFAULT_FROM_EMAIL, [destination], fail_silently=False) != 1:
                raise RuntimeError('Message not accepted')
        else:
            send_sms(destination, body)
    except Exception:
        NotificationSend.objects.filter(pk=pk, status='sending').update(status='failed', last_error='Provider could not accept the message.', next_attempt_at=timezone.now() + timedelta(minutes=min(60, 2 ** job.attempts)))
        return False
    NotificationSend.objects.filter(pk=pk, status='sending').update(status='sent', sent_at=timezone.now(), last_error='')
    return True


def notify_event(event):
    order = event.delivery.package_id.order_id
    package = event.delivery.package_id_id
    updates = {
        'picked_up': ('Package picked up', f'Package {package} in order {order.pk} has been picked up.'),
        'failed': ('Delivery attempt unsuccessful', f'A delivery attempt for package {package} in order {order.pk} was unsuccessful. We will arrange a retry or return.'),
        'delivered': ('Package delivered', f'Package {package} in order {order.pk} has been delivered.'),
        'retry': ('Another delivery attempt arranged', f'Another delivery attempt has been arranged for package {package} in order {order.pk}.'),
        'return': ('Package return arranged', f'Package {package} in order {order.pk} will be returned to its pickup location.'),
        'returned': ('Package returned', f'Package {package} in order {order.pk} has been returned to the sender.'),
    }
    if event.action in updates:
        title, body = updates[event.action]
        publish(order, f'delivery-event:{event.pk}', title, body)
