from django.core.cache import cache
from rest_framework.test import APITestCase

from customer.models import CustomUser, CustomerProfile, DriverProfile
from delivery.models import Delivery
from order.models import Order, Package


class OrderWorkflowTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.customer = CustomUser.objects.create_user('customer@example.com', None, role='customer', is_active=True)
        CustomerProfile.objects.filter(user=self.customer).update(is_complete=True)
        self.customer.refresh_from_db()
        self.driver_user = CustomUser.objects.create_user('driver@example.com', None, role='driver', is_active=True)
        DriverProfile.objects.filter(user=self.driver_user).update(is_complete=True)
        self.driver_user.refresh_from_db()
        self.driver = self.driver_user.driverprofile
        self.order = Order.objects.create(customer_id=self.customer, driver_id=self.driver, order_status='assigned')
        self.package = Package.objects.create(order_id=self.order)
        self.delivery = Delivery.objects.create(package_id=self.package, rider=self.driver)

    def pickup(self, user=None):
        self.client.force_authenticate(user or self.driver_user)
        return self.client.put('/api/v1/order/update/', {'order_id': self.order.pk, 'status': 'picked_up'}, format='json')

    def update_delivery(self, new_status):
        self.client.force_authenticate(self.driver_user)
        return self.client.put('/api/v1/delivery/update/', {'package_id': self.package.pk, 'delivery_status': new_status}, format='json')

    def cancel(self):
        self.client.force_authenticate(self.customer)
        return self.client.put('/api/v1/order/cancel/', {'order_id': self.order.pk, 'cancel_reason': 'Plans changed'}, format='json')

    def test_assigned_driver_can_pick_up_complete_order(self):
        response = self.pickup()
        self.assertEqual(response.status_code, 200, response.data)
        self.order.refresh_from_db()
        self.delivery.refresh_from_db()
        self.assertEqual(self.order.order_status, 'in_transit')
        self.assertEqual(self.delivery.delivery_status, 'picked_up')
        self.assertIsNotNone(self.delivery.picked_up_at)

    def test_empty_order_cannot_be_picked_up(self):
        self.package.delete()
        response = self.pickup()
        self.assertEqual(response.status_code, 400, response.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, 'assigned')

    def test_other_driver_cannot_pick_up_order(self):
        other = CustomUser.objects.create_user('other@example.com', None, role='driver', is_active=True)
        DriverProfile.objects.filter(user=other).update(is_complete=True)
        other.refresh_from_db()
        response = self.pickup(other)
        self.assertEqual(response.status_code, 400, response.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, 'assigned')

    def test_pickup_requires_delivery_for_every_package(self):
        Package.objects.create(order_id=self.order)
        response = self.pickup()
        self.assertEqual(response.status_code, 400, response.data)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.delivery_status, 'assigned')

    def test_packages_allowed_only_before_pickup(self):
        self.client.force_authenticate(self.customer)
        for order_status, expected in [('pending', 201), ('assigned', 201), ('in_transit', 400), ('cancelled', 400), ('delivered', 400)]:
            with self.subTest(status=order_status):
                self.order.order_status = order_status
                self.order.save()
                before = self.order.packages.count()
                response = self.client.post('/api/v1/package/create/', {'order_id': self.order.pk, 'packages': [{'receiver_name': 'Recipient', 'receiver_phone': '+233240000000'}]}, format='json')
                self.assertEqual(response.status_code, expected, response.data)
                self.assertEqual(self.order.packages.count(), before + (expected == 201))

    def test_cancelled_delivery_returns_validation_error(self):
        self.delivery.delivery_status = 'cancelled'
        self.delivery.save()
        response = self.update_delivery('picked_up')
        self.assertEqual(response.status_code, 400, response.data)
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.delivery_status, 'cancelled')

    def test_order_with_missing_delivery_is_not_completed(self):
        Package.objects.create(order_id=self.order)
        self.order.order_status = 'in_transit'
        self.order.save()
        self.delivery.delivery_status = 'picked_up'
        self.delivery.save()
        response = self.update_delivery('delivered')
        self.assertEqual(response.status_code, 201, response.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, 'in_transit')

    def test_order_completes_when_every_package_is_delivered(self):
        self.assertEqual(self.pickup().status_code, 200)
        response = self.update_delivery('delivered')
        self.assertEqual(response.status_code, 201, response.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, 'delivered')

    def test_cancellation_after_pickup_allowed_before_any_delivery(self):
        self.assertEqual(self.pickup().status_code, 200)
        response = self.cancel()
        self.assertEqual(response.status_code, 201, response.data)
        self.order.refresh_from_db()
        self.delivery.refresh_from_db()
        self.assertEqual(self.order.order_status, 'cancelled')
        self.assertEqual(self.delivery.delivery_status, 'cancelled')
        self.assertEqual(self.update_delivery('delivered').status_code, 400)

    def test_cancellation_blocked_after_any_package_delivered(self):
        extra = Package.objects.create(order_id=self.order)
        Delivery.objects.create(package_id=extra, rider=self.driver)
        self.assertEqual(self.pickup().status_code, 200)
        self.assertEqual(self.update_delivery('delivered').status_code, 201)
        response = self.cancel()
        self.assertEqual(response.status_code, 400, response.data)
        self.order.refresh_from_db()
        self.assertEqual(self.order.order_status, 'in_transit')
