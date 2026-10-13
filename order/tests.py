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
        DriverProfile.objects.filter(user=self.driver_user).update(is_complete=True, approval_status="approved", is_approved=True)
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
        return self.client.put('/api/v1/delivery/update/', {'package_id': self.package.pk, 'delivery_status': new_status, 'received_by': 'Test recipient'}, format='json')

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

    def admin_client(self):
        admin = CustomUser.objects.create_user('admin@example.com', None, role='admin', is_active=True, is_staff=True)
        self.client.force_authenticate(admin)

    def another_driver(self):
        user = CustomUser.objects.create_user('next@example.com', None, role='driver', is_active=True)
        profile = DriverProfile.objects.get(user=user)
        profile.is_complete = True
        profile.approval_status = 'approved'
        profile.save()
        return profile

    def assign(self, driver):
        return self.client.put('/api/v1/order/assign/', {'order_id': self.order.pk, 'driver_email': driver.user.email}, format='json')

    def test_manual_reassignment_updates_existing_deliveries(self):
        driver = self.another_driver()
        self.admin_client()
        response = self.assign(driver)
        self.assertEqual(response.status_code, 200, response.data)
        self.order.refresh_from_db()
        self.delivery.refresh_from_db()
        self.assertEqual(self.order.driver_id, driver)
        self.assertEqual(self.delivery.rider, driver)

    def test_reassignment_rejects_active_and_terminal_orders(self):
        driver = self.another_driver()
        self.admin_client()
        for state in ['in_transit', 'cancelled', 'delivered']:
            with self.subTest(state=state):
                self.order.order_status = state
                self.order.save()
                response = self.assign(driver)
                self.assertEqual(response.status_code, 400, response.data)
                self.delivery.refresh_from_db()
                self.assertEqual(self.delivery.rider, self.driver)

    def test_rejected_driver_with_stale_approval_flag_cannot_be_assigned(self):
        driver = self.another_driver()
        driver.approval_status = 'rejected'
        driver.is_approved = True
        driver.save()
        self.admin_client()
        self.assertEqual(self.assign(driver).status_code, 400)

    def test_approval_endpoint_rejects_previously_approved_driver(self):
        self.admin_client()
        response = self.client.put('/api/v1/admin/driver/approve/', {
            'email': self.driver_user.email, 'action': 'reject', 'rejection_reason': 'Expired license'
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.driver.refresh_from_db()
        self.assertEqual(self.driver.approval_status, 'rejected')
        self.assertFalse(self.driver.is_approved)
        self.assertEqual(self.driver.rejection_reason, 'Expired license')

    def test_auto_assignment_selects_least_busy_eligible_driver(self):
        driver = self.another_driver()
        self.client.force_authenticate(self.customer)
        response = self.client.post('/api/v1/order/create/', {'pickup_address': 'Accra'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Order.objects.get(pk=response.data['id']).driver_id, driver)

    def test_driver_can_receive_multiple_active_orders(self):
        self.order.order_status = 'in_transit'
        self.order.save()
        self.client.force_authenticate(self.customer)
        response = self.client.post('/api/v1/order/create/', {'pickup_address': 'Accra'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Order.objects.get(pk=response.data['id']).driver_id, self.driver)

    def test_fallback_uses_order_driver(self):
        self.another_driver()
        package = Package.objects.create(order_id=self.order)
        delivery = Delivery.objects.create(package_id=package)
        delivery.refresh_from_db()
        self.assertEqual(delivery.rider, self.driver)

    def test_fallback_assigns_pending_order_and_delivery_together(self):
        order = Order.objects.create(customer_id=self.customer)
        package = Package.objects.create(order_id=order)
        delivery = Delivery.objects.create(package_id=package)
        order.refresh_from_db()
        delivery.refresh_from_db()
        self.assertEqual(order.driver_id, self.driver)
        self.assertEqual(delivery.rider, self.driver)
        self.assertEqual(order.order_status, 'assigned')

    def test_completed_order_preserves_driver_availability_preference(self):
        self.driver.availability_status = False
        self.driver.save()
        self.assertEqual(self.pickup().status_code, 200)
        self.assertEqual(self.update_delivery('delivered').status_code, 201)
        self.driver.refresh_from_db()
        self.assertFalse(self.driver.availability_status)

    def test_no_eligible_driver_leaves_order_pending(self):
        self.driver.approval_status = 'rejected'
        self.driver.save()
        self.client.force_authenticate(self.customer)
        response = self.client.post('/api/v1/order/create/', {'pickup_address': 'Accra'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        order = Order.objects.get(pk=response.data['id'])
        self.assertIsNone(order.driver_id)
        self.assertEqual(order.order_status, 'pending')

    def test_approval_endpoint_approves_driver(self):
        self.driver.approval_status = 'rejected'
        self.driver.rejection_reason = 'Old reason'
        self.driver.save()
        self.admin_client()
        response = self.client.put('/api/v1/admin/driver/approve/', {
            'email': self.driver_user.email, 'action': 'approve'
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.driver.refresh_from_db()
        self.assertTrue(self.driver.is_approved)
        self.assertEqual(self.driver.approval_status, 'approved')
        self.assertEqual(self.driver.rejection_reason, '')

    def test_auto_assignment_counts_in_transit_orders(self):
        driver = self.another_driver()
        self.order.order_status = 'in_transit'
        self.order.save()
        self.client.force_authenticate(self.customer)
        response = self.client.post('/api/v1/order/create/', {'pickup_address': 'Accra'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Order.objects.get(pk=response.data['id']).driver_id, driver)
