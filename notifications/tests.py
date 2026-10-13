from datetime import timedelta
import io
from unittest.mock import patch
from django.test import override_settings
from django.core.cache import cache
from django.core import mail
from django.db import transaction
from django.utils import timezone
from rest_framework.test import APITestCase
from customer.models import CustomUser, DriverProfile
from order.models import Order, Package
from delivery.models import Delivery, DeliveryEvent, Payment
from .models import Notification, NotificationSend
from .services import publish, dispatch


@override_settings(NOTIFICATION_SEND_IMMEDIATELY=False, AUTO_ROUTE_PLANNING=False, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class NotificationTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = CustomUser.objects.create_user('updates@example.com', '+233241234567', role='customer', is_active=True)
        self.other = CustomUser.objects.create_user('other-updates@example.com', None, role='customer', is_active=True)
        self.driver = CustomUser.objects.create_user('updates-driver@example.com', None, role='driver', is_active=True)
        self.profile = DriverProfile.objects.get(user=self.driver)
        DriverProfile.objects.filter(pk=self.profile.pk).update(is_complete=True)
        self.driver.refresh_from_db()
        self.order = Order.objects.create(customer_id=self.user, driver_id=self.profile, order_status='assigned', pickup_address='Pickup')
        self.package = Package.objects.create(order_id=self.order, delivery_address='Drop')
        self.delivery = Delivery.objects.create(package_id=self.package, rider=self.profile)

    def update(self):
        return publish(self.order, 'test:update', 'Delivery update', 'Your package is on its way.')

    def test_inbox_and_two_verified_channels_created_once(self):
        self.update()
        self.update()
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(set(NotificationSend.objects.values_list('channel', flat=True)), {'email', 'sms'})

    def test_unverified_contacts_are_not_queued(self):
        self.user.email_verified = False
        self.user.phone_verified = False
        self.user.save()
        self.update()
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(NotificationSend.objects.count(), 0)

    def test_email_sent_once(self):
        self.update()
        job = NotificationSend.objects.get(channel='email')
        self.assertTrue(dispatch(job.pk))
        self.assertFalse(dispatch(job.pk))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn('on its way', mail.outbox[0].body)
        job.refresh_from_db()
        self.assertEqual(job.status, 'sent')
        self.assertIsNotNone(job.sent_at)

    @override_settings(TWILIO_ACCOUNT_SID='AC'+'0'*32, TWILIO_AUTH_TOKEN='test', TWILIO_FROM_NUMBER='+15005550006')
    def test_sms_uses_verified_phone(self):
        self.update()
        job = NotificationSend.objects.get(channel='sms')
        with patch('notifications.services.send_sms') as send:
            self.assertTrue(dispatch(job.pk))
        self.assertEqual(send.call_args.args[0], self.user.phone_number)
        self.assertIn('OY Delivery Services', send.call_args.args[1])

    @override_settings(TWILIO_ACCOUNT_SID='', TWILIO_AUTH_TOKEN='', TWILIO_FROM_NUMBER='', TWILIO_MESSAGING_SERVICE_SID='')
    def test_missing_sms_configuration_waits_without_losing_inbox(self):
        self.update()
        job = NotificationSend.objects.get(channel='sms')
        with patch('notifications.services.send_sms') as send:
            self.assertFalse(dispatch(job.pk))
        send.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, 'pending')
        self.assertEqual(job.attempts, 0)
        self.assertIn('configuration required', job.last_error)
        self.assertEqual(Notification.objects.count(), 1)

    def test_provider_failure_retained_for_retry_without_raw_error(self):
        self.update()
        job = NotificationSend.objects.get(channel='email')
        with patch('notifications.services.send_mail', side_effect=RuntimeError('secret credentials from provider')):
            self.assertFalse(dispatch(job.pk))
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertNotIn('secret', job.last_error)
        self.assertEqual(job.attempts, 1)
        self.assertFalse(dispatch(job.pk))
        self.assertTrue(dispatch(job.pk, retry_now=True))
        job.refresh_from_db()
        self.assertEqual(job.status, 'sent')
        self.assertEqual(job.attempts, 2)

    def test_contact_change_prevents_send_to_old_address(self):
        self.update()
        job = NotificationSend.objects.get(channel='email')
        CustomUser.objects.filter(pk=self.user.pk).update(email='changed@example.com')
        with patch('notifications.services.send_mail') as send:
            self.assertFalse(dispatch(job.pk))
        send.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, 'skipped')

    def test_recent_claim_and_attempt_limit_prevent_duplicate_send(self):
        self.update()
        job = NotificationSend.objects.get(channel='email')
        NotificationSend.objects.filter(pk=job.pk).update(status='sending', claimed_at=timezone.now())
        self.assertFalse(dispatch(job.pk, retry_now=True))
        NotificationSend.objects.filter(pk=job.pk).update(status='failed', attempts=5)
        self.assertFalse(dispatch(job.pk, retry_now=True))

    def test_abandoned_claim_can_be_recovered(self):
        self.update()
        job = NotificationSend.objects.get(channel='email')
        NotificationSend.objects.filter(pk=job.pk).update(status='sending', claimed_at=timezone.now()-timedelta(minutes=16))
        self.assertTrue(dispatch(job.pk))

    def test_rollback_leaves_no_notifications_or_jobs(self):
        try:
            with transaction.atomic():
                self.update()
                raise RuntimeError('rollback')
        except RuntimeError:
            pass
        self.assertFalse(Notification.objects.exists())
        self.assertFalse(NotificationSend.objects.exists())

    @override_settings(NOTIFICATION_SEND_IMMEDIATELY=True)
    def test_send_occurs_after_commit_and_failure_does_not_fail_event(self):
        with patch('notifications.services.dispatch', side_effect=RuntimeError('provider unavailable')) as send:
            with self.captureOnCommitCallbacks(execute=True):
                self.update()
                send.assert_not_called()
        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(send.call_count, 2)

    def test_lifecycle_events_generate_customer_updates(self):
        for action in ['failed', 'retry', 'return', 'returned', 'delivered']:
            DeliveryEvent.objects.create(delivery=self.delivery, action=action, actor=self.driver)
        self.assertEqual(Notification.objects.filter(customer=self.user).count(), 5)
        self.assertEqual(NotificationSend.objects.count(), 10)

    def test_order_pickup_sends_one_order_update_for_multiple_packages(self):
        second = Package.objects.create(order_id=self.order, delivery_address='Other stop')
        Delivery.objects.create(package_id=second, rider=self.profile)
        self.client.force_authenticate(self.driver)
        response = self.client.put('/api/v1/order/update/', dict(order_id=self.order.pk, status='picked_up'), format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Notification.objects.count(), 1)
        self.assertIn('All packages', Notification.objects.get().body)

    def test_payment_confirmed_update_created_once(self):
        payment = Payment.objects.create(package_id=self.package, payment_method='cash', amount=35, payment_status='paid')
        payment.save()
        self.assertEqual(Notification.objects.count(), 1)
        self.assertIn('GHS 35.00', Notification.objects.get().body)

    def test_inbox_and_read_action_are_private(self):
        notification = self.update()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get('/api/v1/notifications/').data['count'], 0)
        self.assertEqual(self.client.post(f'/api/v1/notifications/{notification.pk}/read/', {}).status_code, 404)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get('/api/v1/notifications/').data['count'], 1)
        self.assertEqual(self.client.post(f'/api/v1/notifications/{notification.pk}/read/', {}).status_code, 200)
        notification.refresh_from_db()
        first_read = notification.read_at
        self.client.post(f'/api/v1/notifications/{notification.pk}/read/', {})
        notification.refresh_from_db()
        self.assertEqual(notification.read_at, first_read)

    def test_inbox_page_and_unread_count(self):
        self.update()
        self.client.force_login(self.user)
        response = self.client.get('/notifications/')
        self.assertContains(response, 'Your package is on its way.')
        self.assertContains(response, 'Updates (1)')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get('/notifications/'), 'Your package is on its way.')

    @override_settings(TWILIO_ACCOUNT_SID='', TWILIO_AUTH_TOKEN='', TWILIO_FROM_NUMBER='', TWILIO_MESSAGING_SERVICE_SID='')
    def test_retry_command_sends_due_email_without_resending(self):
        from django.core.management import call_command
        self.update()
        output = io.StringIO()
        call_command('send_notifications', stdout=output)
        self.assertIn('sent 1', output.getvalue())
        call_command('send_notifications', stdout=output)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(TWILIO_ACCOUNT_SID='AC'+'0'*32, TWILIO_AUTH_TOKEN='test', TWILIO_FROM_NUMBER='+15005550006')
    def test_failed_sms_can_retry_after_backoff(self):
        self.update()
        job = NotificationSend.objects.get(channel='sms')
        with patch('notifications.services.send_sms', side_effect=RuntimeError('failure')):
            self.assertFalse(dispatch(job.pk))
        NotificationSend.objects.filter(pk=job.pk).update(next_attempt_at=timezone.now()-timedelta(seconds=1))
        with patch('notifications.services.send_sms') as send:
            self.assertTrue(dispatch(job.pk))
        send.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.attempts, 2)


    def test_payment_notification_accepts_model_amount_as_string(self):
        Payment.objects.create(package_id=self.package, payment_method='cash', amount='35.00', payment_status='paid')
        self.assertIn('GHS 35.00', Notification.objects.get().body)
