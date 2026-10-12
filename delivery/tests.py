from rest_framework.test import APITestCase

from customer.models import CustomUser, CustomerProfile, DriverProfile
from delivery.models import Delivery
from order.models import Order, Package


class DeliveryOwnershipTests(APITestCase):
    def setUp(self):
        self.customer = self.make_customer('owner@example.com')
        other = self.make_customer('other@example.com')
        self.driver = self.make_driver('driver@example.com')
        self.other_driver = self.make_driver('other-driver@example.com')
        self.own_package = self.make_package(self.customer, self.driver)
        self.other_package = self.make_package(other, self.other_driver)
        self.client.force_authenticate(self.customer)

    def make_customer(self, email):
        user = CustomUser.objects.create_user(email, None, role='customer', is_active=True)
        CustomerProfile.objects.update_or_create(user=user, defaults={'is_complete': True})
        user.refresh_from_db()
        return user

    def make_driver(self, email):
        user = CustomUser.objects.create_user(email, None, role='driver', is_active=True)
        profile, _ = DriverProfile.objects.update_or_create(
            user=user, defaults={'is_complete': True, 'approval_status': 'approved'}
        )
        return profile

    def make_package(self, customer, driver):
        order = Order.objects.create(customer_id=customer, driver_id=driver, order_status='assigned')
        return Package.objects.create(order_id=order, receiver_name=customer.email)

    def create_deliveries(self, *packages):
        return self.client.post('/api/v1/delivery/create/', {
            'deliveries': [{'package_id': p.pk, 'address': 'Accra'} for p in packages]
        }, format='json')

    def test_owner_can_create_delivery(self):
        response = self.create_deliveries(self.own_package)
        self.assertEqual(response.status_code, 201, response.data)
        delivery = Delivery.objects.get(package_id=self.own_package)
        self.assertEqual(delivery.rider, self.driver)

    def test_other_customers_package_is_rejected(self):
        response = self.create_deliveries(self.other_package)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Delivery.objects.exists())

    def test_mixed_batch_creates_nothing(self):
        response = self.create_deliveries(self.own_package, self.other_package)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Delivery.objects.exists())

    def test_driver_sees_only_assigned_deliveries(self):
        own = Delivery.objects.create(package_id=self.own_package, rider=self.driver)
        Delivery.objects.create(package_id=self.other_package, rider=self.other_driver)
        self.client.force_authenticate(self.driver.user)
        response = self.client.get('/api/v1/search/delivery/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item['id'] for item in response.data['results']], [own.pk])

    def test_driver_sees_only_assigned_packages(self):
        self.client.force_authenticate(self.driver.user)
        response = self.client.get('/api/v1/search/package/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['receiver_name'], self.own_package.receiver_name)
