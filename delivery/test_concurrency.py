from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from django.core.cache import cache
from django.db import connections, close_old_connections, connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError
from customer.models import CustomUser, CustomerProfile, DriverProfile, EmailOTP
from customer.services import send_otp, verify_otp, confirm_account_token
from order.models import Order, Package, DeliveryQuote
from delivery.models import Delivery, Payment


class ConcurrentWorkflowTests(TransactionTestCase):
    def setUp(self):
        if 'memory' in str(connection.settings_dict['NAME']):
            self.skipTest('Concurrent SQLite tests require a disk database via SQLITE_TEST_DATABASE.')
        cache.clear()
        self.customer = CustomUser.objects.create_user('race-customer@example.com', None, role='customer', is_active=True)
        CustomerProfile.objects.filter(user=self.customer).update(is_complete=True)
        self.driver = CustomUser.objects.create_user('race-driver@example.com', None, role='driver', is_active=True)
        DriverProfile.objects.filter(user=self.driver).update(is_complete=True)
        self.order = Order.objects.create(customer_id=self.customer, driver_id=DriverProfile.objects.get(user=self.driver), order_status='assigned', pickup_address='Accra')
        self.package = Package.objects.create(order_id=self.order, delivery_address='Osu')

    def race(self, *operations):
        barrier = Barrier(len(operations))
        def run(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return operation()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            futures = [pool.submit(run, operation) for operation in operations]
            return [future.result(timeout=30) for future in futures]

    def request(self, user, path, payload, method='post'):
        client = APIClient()
        client.force_authenticate(CustomUser.objects.get(pk=user.pk))
        return getattr(client, method)(path, payload, format='json').status_code

    def delivery(self):
        return Delivery.objects.create(package_id=self.package, rider=self.order.driver_id)

    def quote(self):
        return DeliveryQuote.objects.create(package=self.package, amount=35, distance_meters=9000, pickup_address='Accra', delivery_address='Osu', outside_accra=False, reason='Test tariff')

    def test_two_delivery_creations_create_exactly_one_record(self):
        operation = lambda: self.request(self.customer, '/api/v1/delivery/create/', {'deliveries': [{'package_id': self.package.pk}]})
        self.assertEqual(sorted(self.race(operation, operation)), [201, 400])
        self.assertEqual(Delivery.objects.filter(package_id=self.package).count(), 1)

    def test_two_payment_creations_create_exactly_one_record(self):
        self.quote()
        operation = lambda: self.request(self.customer, '/api/v1/payment/create/', {'package_id': self.package.pk, 'payment_method': 'cash'})
        self.assertEqual(sorted(self.race(operation, operation)), [201, 400])
        self.assertEqual(Payment.objects.filter(package_id=self.package).count(), 1)

    def test_two_payment_confirmations_succeed_only_once(self):
        self.delivery()
        payment = Payment.objects.create(package_id=self.package, amount=35, payment_method='cash')
        operation = lambda: self.request(self.driver, f'/api/v1/payment/{payment.pk}/confirm/', {})
        self.assertEqual(sorted(self.race(operation, operation)), [200, 400])
        payment.refresh_from_db()
        self.assertEqual(payment.payment_status, 'paid')
        self.assertEqual(payment.confirmed_by, self.driver)

    def test_cancel_and_deliver_cannot_produce_conflicting_states(self):
        delivery = self.delivery()
        delivery.delivery_status = 'picked_up'
        delivery.save()
        self.order.order_status = 'in_transit'
        self.order.save()
        cancel = lambda: self.request(self.customer, '/api/v1/order/cancel/', {'order_id': self.order.pk, 'cancel_reason': 'Cancelled'}, 'put')
        deliver = lambda: self.request(self.driver, '/api/v1/delivery/update/', {'package_id': self.package.pk, 'delivery_status': 'delivered'}, 'put')
        self.assertEqual(sorted(self.race(cancel, deliver)), [201, 400])
        self.order.refresh_from_db()
        delivery.refresh_from_db()
        self.assertIn((self.order.order_status, delivery.delivery_status), [('cancelled', 'cancelled'), ('delivered', 'delivered')])

    def test_two_otp_resends_leave_only_one_code(self):
        with patch('customer.services.send_mail'):
            operation = lambda: send_otp(self.customer, 'password_reset')
            self.race(operation, operation)
        self.assertEqual(EmailOTP.objects.filter(user=self.customer, otp_purpose='password_reset').count(), 1)

    def test_same_otp_verifies_only_once(self):
        EmailOTP.objects.create(user=self.customer, otp='123456', otp_purpose='password_reset')
        operation = lambda: self.request(self.customer, '/api/v1/password-reset/verify/', {'email': self.customer.email, 'otp': '123456'})
        self.assertEqual(sorted(self.race(operation, operation)), [200, 400])

    def test_confirmation_token_is_consumed_only_once(self):
        EmailOTP.objects.create(user=self.customer, otp='123456', otp_purpose='password_reset')
        token = verify_otp(self.customer.email, '123456', 'password_reset')
        actions = []
        def action(user):
            actions.append(user.pk)
            user.first_name = 'Confirmed'
            user.save(update_fields=['first_name'])
        def operation():
            try:
                confirm_account_token(token, 'password_reset', action)
                return 200
            except ValidationError:
                return 400
        self.assertEqual(sorted(self.race(operation, operation)), [200, 400])
        self.assertEqual(actions, [self.customer.pk])

    def test_delivery_save_rechecks_cancelled_order(self):
        from types import SimpleNamespace
        from delivery.serializers import CreateDeliveriesSerializer
        serializer = CreateDeliveriesSerializer(data={'deliveries': [{'package_id': self.package.pk}]}, context={'request': SimpleNamespace(user=self.customer)})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        Order.objects.filter(pk=self.order.pk).update(order_status='cancelled')
        with self.assertRaises(ValidationError):
            serializer.save()
        self.assertFalse(Delivery.objects.filter(package_id=self.package).exists())

    def test_delivery_save_uses_reassigned_driver(self):
        from types import SimpleNamespace
        from delivery.serializers import CreateDeliveriesSerializer
        serializer = CreateDeliveriesSerializer(data={'deliveries': [{'package_id': self.package.pk}]}, context={'request': SimpleNamespace(user=self.customer)})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        other = CustomUser.objects.create_user('new-driver@example.com', None, role='driver', is_active=True)
        profile = DriverProfile.objects.get(user=other)
        Order.objects.filter(pk=self.order.pk).update(driver_id=profile)
        result = serializer.save()
        self.assertEqual(result[0].rider, profile)

    def test_duplicate_packages_in_batch_create_nothing(self):
        status = self.request(self.customer, '/api/v1/delivery/create/', {'deliveries': [{'package_id': self.package.pk}, {'package_id': self.package.pk}]})
        self.assertEqual(status, 400)
        self.assertFalse(Delivery.objects.filter(package_id=self.package).exists())
