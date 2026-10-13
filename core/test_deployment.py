import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.core.management import call_command
from django.core.cache import cache
from django.db import DatabaseError
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory
from customer.models import CustomUser, CustomerProfile, DriverProfile
from customer.throttles import LoginThrottle, OTPRegisterThrottle, OTPVerifyThrottle
from order.models import Order, Package
from delivery.models import Delivery, Payment, DeliveryEvent
from notifications.models import Notification


@override_settings(NOTIFICATION_SEND_IMMEDIATELY=False, AUTO_ROUTE_PLANNING=False)
class DeploymentTrialTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_health_success_and_database_failure_do_not_leak_details(self):
        self.assertEqual(self.client.get('/health/').json(), {'status': 'ok'})
        with patch('core.health.connections') as connections:
            connections.__getitem__.return_value.cursor.side_effect = DatabaseError('private connection string')
            response = self.client.get('/health/')
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, 'private', status_code=503)

    def test_login_and_otp_scopes_stay_separate_and_bounded(self):
        request = APIRequestFactory().post('/api/v1/auth/login/', {})
        login, register, verify = LoginThrottle(), OTPRegisterThrottle(), OTPVerifyThrottle()
        self.assertEqual(len({t.get_cache_key(request, None) for t in [login, register, verify]}), 3)
        for _ in range(5):
            self.assertTrue(login.allow_request(request, None))
        self.assertFalse(login.allow_request(request, None))
        for _ in range(3):
            self.assertTrue(register.allow_request(request, None))
        self.assertFalse(register.allow_request(request, None))
        self.assertTrue(verify.allow_request(request, None))

    def test_restore_preserves_profiles_payments_and_history_without_messages(self):
        customer = CustomUser.objects.create_user('restore@example.com', None, role='customer', is_active=True)
        driver = CustomUser.objects.create_user('restore-driver@example.com', None, role='driver', is_active=True)
        profile = DriverProfile.objects.get(user=driver)
        order = Order.objects.create(customer_id=customer, driver_id=profile)
        package = Package.objects.create(order_id=order)
        delivery = Delivery.objects.create(package_id=package, rider=profile)
        Payment.objects.create(package_id=package, amount=35, payment_method='cash', payment_status='paid')
        DeliveryEvent.objects.create(delivery=delivery, action='delivered', actor=driver)
        apps = ['customer.customuser', 'customer.customerprofile', 'customer.driverprofile', 'order.order', 'order.package', 'delivery.delivery', 'delivery.payment', 'delivery.deliveryevent']
        with TemporaryDirectory() as folder:
            fixture = Path(folder)/'backup.json'
            call_command('dumpdata', *apps, output=str(fixture), verbosity=0)
            # Loading a backup over these existing rows invokes raw fixture signals.
            # No external notifications or assignments should be regenerated.
            before_notifications = Notification.objects.count()
            before_profiles = CustomerProfile.objects.count()
            with patch('delivery.signals.assign_rider_to_delivery') as assign, patch('notifications.signals.publish') as publish:
                call_command('loaddata', str(fixture), verbosity=0)
            assign.assert_not_called()
            publish.assert_not_called()
            self.assertEqual(Notification.objects.count(), before_notifications)
            self.assertEqual(CustomerProfile.objects.count(), before_profiles)
            self.assertEqual(DeliveryEvent.objects.count(), 1)

    def test_notification_watch_mode_can_run_one_cycle_and_stop(self):
        import io
        output = io.StringIO()
        with patch('notifications.management.commands.send_notifications.time.sleep', side_effect=KeyboardInterrupt):
            call_command('send_notifications', watch=True, interval=60, stdout=output)
        self.assertIn('Checked 0', output.getvalue())

    def test_browser_login_is_throttled_before_authentication(self):
        from django.http import HttpResponse
        with patch('django.contrib.auth.views.LoginView.post', return_value=HttpResponse('ok')) as authenticate:
            responses = [self.client.post('/login/', {'username': 'trial@example.com', 'password': 'incorrect'}) for _ in range(6)]
        self.assertEqual([response.status_code for response in responses], [200]*5+[429])
        self.assertEqual(authenticate.call_count, 5)
        self.assertIn('Retry-After', responses[-1])

    def test_session_order_write_requires_csrf_token(self):
        from django.test import Client
        password = 'Csrf!Trial2026'
        user = CustomUser.objects.create_user('csrf-trial@example.com', '+233241234565', password=password, role='customer', is_active=True)
        CustomerProfile.objects.filter(user=user).update(customer_name='Trial', address='Accra', is_complete=True)
        client = Client(enforce_csrf_checks=True)
        client.get('/login/')
        token = client.cookies['csrftoken'].value
        login = client.post('/login/', {'username': user.email, 'password': password, 'csrfmiddlewaretoken': token})
        self.assertEqual(login.status_code, 302)
        data = json.dumps({'pickup_address': 'Trial pickup'})
        self.assertEqual(client.post('/api/v1/order/create/', data, content_type='application/json').status_code, 403)
        self.assertEqual(client.post('/api/v1/order/create/', data, content_type='application/json', HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value).status_code, 201)
