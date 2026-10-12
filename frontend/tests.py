from django.test import TestCase, Client
from django.core.cache import cache
from django.urls import reverse
from customer.models import CustomUser, CustomerProfile, DriverProfile
from order.models import Order, Package
from delivery.models import Delivery


class FrontendTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = CustomUser.objects.create_user('web@example.com', None, password='Web!Password934', role='customer', is_active=True)
        CustomerProfile.objects.filter(user=self.user).update(is_complete=True)
        self.other = CustomUser.objects.create_user('other@example.com', None, role='customer', is_active=True)
        self.driver = CustomUser.objects.create_user('driver@example.com', None, role='driver', is_active=True)
        self.order = Order.objects.create(customer_id=self.user, pickup_address='Accra', driver_id=self.driver.driverprofile, order_status='assigned')
        self.package = Package.objects.create(order_id=self.order, delivery_address='Osu', receiver_name='Recipient')
        Delivery.objects.create(package_id=self.package, rider=self.driver.driverprofile)

    def test_login_and_public_pages_render(self):
        self.assertEqual(self.client.get('/').status_code, 302)
        for url in ['/login/', '/register/', '/password-reset/']:
            self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post('/login/', {'username': self.user.email, 'password': 'Web!Password934'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_customer_pages_and_ownership(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get('/'), self.order.pk)
        self.assertContains(self.client.get(f'/orders/{self.order.pk}/'), 'Get delivery quote')
        self.assertEqual(self.client.get('/profile/').status_code, 200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f'/orders/{self.order.pk}/').status_code, 404)

    def test_driver_and_staff_pages_render(self):
        self.client.force_login(self.driver)
        self.assertContains(self.client.get(f'/orders/{self.order.pk}/'), 'Mark order picked up')
        self.assertEqual(self.client.get('/profile/').status_code, 200)
        admin = CustomUser.objects.create_superuser('admin@example.com', None, password='Admin!Password934')
        self.client.force_login(admin)
        self.assertContains(self.client.get('/'), 'Driver approvals')
        self.assertEqual(self.client.get(f'/orders/{self.order.pk}/').status_code, 200)

    def test_session_api_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        page = client.get('/')
        self.assertEqual(page.status_code, 200)
        response = client.post('/api/v1/order/create/', {'pickup_address': 'Accra'}, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        response = client.post('/api/v1/order/create/', {'pickup_address': 'Accra'}, content_type='application/json', HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 201, response.content)

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/logout/').status_code, 405)
        self.assertEqual(self.client.post('/logout/').status_code, 302)

    def test_momo_id_visible_and_capture_form_restricted(self):
        from delivery.models import Payment
        Payment.objects.create(package_id=self.package, amount=35, payment_method='mobile_money', transaction_reference='MOMO-WEB-123')
        self.client.force_login(self.user)
        response = self.client.get(f'/orders/{self.order.pk}/')
        self.assertContains(response, 'MOMO-WEB-123')
        self.assertNotContains(response, 'Save transaction ID')
        self.client.force_login(self.driver)
        response = self.client.get(f'/orders/{self.order.pk}/')
        self.assertContains(response, 'Save transaction ID')
        self.assertContains(response, 'MOMO-WEB-123')
