import io
import tempfile
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from django.test import override_settings
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import FileSystemStorage
from rest_framework.test import APITestCase
from customer.models import CustomUser, DriverProfile, CustomerProfile
from order.models import Order, Package
from .models import Delivery, DeliveryEvent, Payment
from .routing import collect_stops, current_route


@override_settings(AUTO_ROUTE_PLANNING=False)
class DeliveryLifecycleTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.customer = CustomUser.objects.create_user('handover-customer@example.com', None, role='customer', is_active=True)
        CustomerProfile.objects.filter(user=self.customer).update(is_complete=True)
        self.driver = CustomUser.objects.create_user('handover-driver@example.com', None, role='driver', is_active=True)
        self.profile = DriverProfile.objects.get(user=self.driver)
        DriverProfile.objects.filter(pk=self.profile.pk).update(is_complete=True)
        self.driver.refresh_from_db()
        self.customer.refresh_from_db()
        self.staff = CustomUser.objects.create_user('handover-admin@example.com', None, role='admin', is_active=True, is_staff=True)
        self.outsider = CustomUser.objects.create_user('handover-outsider@example.com', None, role='customer', is_active=True)
        self.order = Order.objects.create(customer_id=self.customer, driver_id=self.profile, order_status='in_transit', pickup_address='Sender address')
        self.package = Package.objects.create(order_id=self.order, delivery_address='Receiver address', receiver_name='Intended recipient')
        self.delivery = Delivery.objects.create(package_id=self.package, rider=self.profile, delivery_status='picked_up')
        self.storage_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.storage_dir.cleanup)
        field = Delivery._meta.get_field('proof_photo')
        old_storage = field.storage
        field.storage = FileSystemStorage(location=self.storage_dir.name)
        self.addCleanup(setattr, field, 'storage', old_storage)
        self.client.force_authenticate(self.driver)

    def update(self, status, **extra):
        return self.client.put('/api/v1/delivery/update/', dict(package_id=self.package.pk, delivery_status=status, **extra), format='multipart' if 'proof_photo' in extra else 'json')

    def resolve(self, action='retry', reason='Agreed with customer'):
        return self.client.post(f'/api/v1/delivery/{self.delivery.pk}/resolution/', dict(action=action, reason=reason), format='json')

    def photo(self):
        stream = io.BytesIO()
        Image.new('RGB', (8, 8), 'white').save(stream, format='PNG')
        return SimpleUploadedFile('proof.png', stream.getvalue(), content_type='image/png')

    def record_failure(self):
        response = self.update('failed', failure_reason='receiver_unavailable', delivery_notes='No one at the door')
        self.assertEqual(response.status_code, 201, response.data)
        self.delivery.refresh_from_db()

    def test_completion_requires_recipient_and_records_server_time(self):
        self.assertEqual(self.update('delivered').status_code, 400)
        response = self.update('delivered', received_by='Actual recipient')
        self.assertEqual(response.status_code, 201, response.data)
        self.delivery.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.delivery.received_by, 'Actual recipient')
        self.assertIsNotNone(self.delivery.delivered_at)
        self.assertEqual(self.delivery.attempt_count, 1)
        self.assertEqual(self.order.order_status, 'delivered')
        self.assertEqual(self.delivery.events.get().actor, self.driver)

    def test_photo_is_optional(self):
        self.assertEqual(self.update('delivered', received_by='Recipient').status_code, 201)
        self.delivery.refresh_from_db()
        self.assertFalse(self.delivery.proof_photo)

    def test_invalid_and_oversize_photos_rejected(self):
        for upload in [SimpleUploadedFile('fake.png', b'not an image', content_type='image/png'), SimpleUploadedFile('large.jpg', b'x' * (5*1024*1024+1))]:
            with self.subTest(name=upload.name):
                self.assertEqual(self.update('delivered', received_by='Recipient', proof_photo=upload).status_code, 400)
        self.assertEqual(self.delivery.events.count(), 0)
        self.assertEqual(list(Path(self.storage_dir.name).rglob('*.jpg')), [])

    def test_photo_reencoded_and_access_limited_to_involved_accounts(self):
        self.assertEqual(self.update('delivered', received_by='Recipient', proof_photo=self.photo()).status_code, 201)
        self.delivery.refresh_from_db()
        self.assertTrue(self.delivery.proof_photo.name.endswith('.jpg'))
        url = f'/api/v1/delivery/{self.delivery.pk}/proof/'
        for user in [self.driver, self.customer, self.staff]:
            self.client.force_authenticate(user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'image/jpeg')
            self.assertEqual(response['Cache-Control'], 'private, no-store')
            content = b''.join(response.streaming_content)
            with Image.open(io.BytesIO(content)) as image:
                self.assertEqual(image.format, 'JPEG')
                self.assertFalse(image.getexif())
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(url).status_code, [401, 403])

    def test_failure_reason_required_and_other_needs_details(self):
        self.assertEqual(self.update('failed').status_code, 400)
        self.assertEqual(self.update('failed', failure_reason='other').status_code, 400)
        self.assertEqual(self.update('failed', failure_reason='invalid').status_code, 400)
        self.assertEqual(self.update('failed', failure_reason='other', delivery_notes='Vehicle breakdown').status_code, 201)

    def test_failed_package_stays_in_transit_and_leaves_delivery_route(self):
        self.record_failure()
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, 'in_transit')
        self.assertEqual(self.delivery.attempt_count, 1)
        self.assertEqual(collect_stops(self.profile.pk)[0], [])
        event = self.delivery.events.get()
        self.assertIn('No one at the door', event.reason)
        self.assertEqual(event.action, 'failed')
        self.assertIsNone(self.delivery.delivered_at)

    def test_only_staff_can_authorize_retry_or_return(self):
        self.record_failure()
        for user in [self.driver, self.customer, self.outsider]:
            self.client.force_authenticate(user)
            self.assertEqual(self.resolve().status_code, 403)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.delivery_status, 'failed')

    def test_retry_preserves_failed_attempt_and_needs_no_second_pickup(self):
        self.record_failure()
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.resolve().status_code, 200)
        stops, _ = collect_stops(self.profile.pk)
        self.assertEqual(len(stops), 1)
        self.assertIsNone(stops[0]['requires'])
        self.client.force_authenticate(self.driver)
        self.assertEqual(self.update('delivered', received_by='Recipient').status_code, 201)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.attempt_count, 2)
        self.assertEqual(list(self.delivery.events.values_list('action', flat=True)), ['failed', 'retry', 'delivered'])
        self.assertEqual(list(self.delivery.events.values_list('attempt_number', flat=True)), [1, 1, 2])

    def test_return_route_and_sender_acknowledgement(self):
        self.record_failure()
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.resolve('return').status_code, 200)
        stops, _ = collect_stops(self.profile.pk)
        self.assertEqual(stops[0]['kind'], 'return')
        self.assertEqual(stops[0]['address'], 'Sender address')
        self.client.force_authenticate(self.driver)
        self.assertEqual(self.update('delivered', received_by='Recipient').status_code, 400)
        self.assertEqual(self.update('returned').status_code, 400)
        self.assertEqual(self.update('returned', received_by='Sender').status_code, 201)
        self.delivery.refresh_from_db()
        self.order.refresh_from_db()
        self.assertIsNotNone(self.delivery.returned_at)
        self.assertIsNone(self.delivery.delivered_at)
        self.assertEqual(self.order.order_status, 'returned')
        self.assertEqual(collect_stops(self.profile.pk)[0], [])

    def test_mixed_delivered_and_returned_packages_close_with_returns(self):
        package2 = Package.objects.create(order_id=self.order, delivery_address='Other recipient')
        Delivery.objects.create(package_id=package2, rider=self.profile, delivery_status='delivered')
        self.record_failure()
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.resolve('return').status_code, 200)
        self.client.force_authenticate(self.driver)
        self.assertEqual(self.update('returned', received_by='Sender').status_code, 201)
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, 'completed_returns')

    def test_duplicate_completion_or_resolution_does_not_duplicate_history(self):
        self.record_failure()
        self.assertEqual(self.update('failed', failure_reason='receiver_unavailable').status_code, 400)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.resolve().status_code, 200)
        self.assertEqual(self.resolve().status_code, 400)
        self.client.force_authenticate(self.driver)
        self.assertEqual(self.update('delivered', received_by='Recipient').status_code, 201)
        self.assertEqual(self.update('delivered', received_by='Changed recipient').status_code, 400)
        self.assertEqual(self.delivery.events.count(), 3)

    def test_history_is_private(self):
        self.record_failure()
        url = f'/api/v1/delivery/{self.delivery.pk}/history/'
        for user in [self.customer, self.driver, self.staff]:
            self.client.force_authenticate(user)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.data), 1)
        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_outsider_driver_cannot_complete_delivery(self):
        other = CustomUser.objects.create_user('other-handover-driver@example.com', None, role='driver', is_active=True)
        DriverProfile.objects.filter(user=other).update(is_complete=True)
        other.refresh_from_db()
        self.client.force_authenticate(other)
        self.assertEqual(self.update('delivered', received_by='Recipient').status_code, 400)
        self.assertFalse(DeliveryEvent.objects.exists())

    def test_failure_does_not_change_payment(self):
        payment = Payment.objects.create(package_id=self.package, payment_method='cash', amount=35)
        self.record_failure()
        payment.refresh_from_db()
        self.assertEqual(payment.payment_status, 'pending')
        self.assertEqual(payment.amount, 35)

    def test_failed_delivery_cannot_be_silently_cancelled(self):
        self.record_failure()
        self.client.force_authenticate(self.customer)
        response = self.client.put('/api/v1/order/cancel/', dict(order_id=self.order.pk, cancel_reason='Cancel instead of return'), format='json')
        self.assertEqual(response.status_code, 400)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.delivery_status, 'failed')

    def test_photo_cleaned_up_if_history_transaction_fails(self):
        with patch('delivery.lifecycle.DeliveryEvent.objects.create', side_effect=RuntimeError('test rollback')):
            with self.assertRaises(RuntimeError):
                self.update('delivered', received_by='Recipient', proof_photo=self.photo())
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.delivery_status, 'picked_up')
        self.assertEqual(list(Path(self.storage_dir.name).rglob('*.jpg')), [])

    def test_driver_and_staff_pages_render_actions(self):
        self.client.force_login(self.driver)
        response = self.client.get(f'/orders/{self.order.pk}/')
        self.assertContains(response, 'Received by')
        self.assertContains(response, 'Optional delivery photo')
        self.assertContains(response, 'Delivery attempt failed')
        self.record_failure()
        self.client.force_login(self.staff)
        response = self.client.get(f'/orders/{self.order.pk}/')
        self.assertContains(response, 'Authorize another delivery attempt')
        self.assertContains(response, 'Delivery history')
