from unittest.mock import patch
from django.core.cache import cache
from rest_framework.test import APITestCase
from customer.models import CustomUser, CustomerProfile, DriverProfile
from customer.serializers import CustomerProfileSerializer
from order.models import Order, Package
from delivery.models import Delivery
from order.services import eligible_drivers


class ProfileValidationTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.customer = CustomUser.objects.create_user('profile@example.com', '+233240000001', password='Profile!Password739', role='customer', is_active=True, first_name='Ama', last_name='Mensah')
        CustomerProfile.objects.filter(user=self.customer).update(customer_name='Ama Mensah', address='Accra', is_complete=True)
        self.driver = CustomUser.objects.create_user('profile-driver@example.com', '+233240000002', password='Profile!Password739', role='driver', is_active=True)
        DriverProfile.objects.filter(user=self.driver).update(vehicle_type='Motorbike', vehicle_number='GR-1234', license_number='LIC-1234', is_complete=True, is_approved=True, approval_status='approved')
        self.customer.refresh_from_db()
        self.driver.refresh_from_db()

    def update(self, user, data):
        self.client.force_authenticate(user)
        return self.client.put('/api/v1/profile/update/', data, format='json')

    def test_clearing_customer_address_revokes_completion(self):
        response = self.update(self.customer, {'address': ''})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data['profile']['is_complete'])
        self.customer.refresh_from_db()
        response = self.client.post('/api/v1/order/create/', {'pickup_address': 'Accra'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_restoring_required_fields_recomputes_completion(self):
        CustomerProfile.objects.filter(user=self.customer).update(address='', is_complete=False)
        response = self.update(self.customer, {'address': 'Osu'})
        self.assertTrue(response.data['profile']['is_complete'])
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.customer_profile.customer_name, 'Ama Mensah')

    def test_duplicate_phone_is_validation_error_and_preserves_user(self):
        response = self.update(self.customer, {'phone_number': self.driver.phone_number, 'first_name': 'Changed'})
        self.assertEqual(response.status_code, 400, response.data)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, 'Ama')
        self.assertEqual(self.customer.phone_number, '+233240000001')

    def test_unchanged_phone_is_valid(self):
        self.assertEqual(self.update(self.customer, {'phone_number': self.customer.phone_number}).status_code, 200)

    def test_each_driver_credential_change_resets_approval(self):
        for field in ['vehicle_type', 'vehicle_number', 'license_number']:
            with self.subTest(field=field):
                DriverProfile.objects.filter(user=self.driver).update(approval_status='approved', is_approved=True)
                response = self.update(self.driver, {field: 'New details'})
                self.assertEqual(response.status_code, 200, response.data)
                profile = DriverProfile.objects.get(user=self.driver)
                self.assertEqual(profile.approval_status, 'pending')
                self.assertFalse(profile.is_approved)
                self.assertFalse(eligible_drivers().filter(pk=profile.pk).exists())

    def test_availability_or_unchanged_credentials_do_not_reset_approval(self):
        response = self.update(self.driver, {'availability_status': False, 'license_number': 'LIC-1234'})
        self.assertEqual(response.status_code, 200, response.data)
        profile = DriverProfile.objects.get(user=self.driver)
        self.assertEqual(profile.approval_status, 'approved')
        self.assertTrue(profile.is_approved)

    def test_clearing_driver_credentials_revokes_completion(self):
        response = self.update(self.driver, {'license_number': ''})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data['profile']['is_complete'])

    def test_pending_reapproval_driver_can_finish_assigned_delivery(self):
        profile = self.driver.driverprofile
        order = Order.objects.create(customer_id=self.customer, driver_id=profile, order_status='in_transit')
        package = Package.objects.create(order_id=order)
        Delivery.objects.create(package_id=package, rider=profile, delivery_status='picked_up')
        self.assertEqual(self.update(self.driver, {'license_number': 'NEW-LICENSE'}).status_code, 200)
        self.driver.refresh_from_db()
        response = self.client.put('/api/v1/delivery/update/', {'package_id': package.pk, 'delivery_status': 'delivered'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        order.refresh_from_db()
        self.assertEqual(order.order_status, 'delivered')

    def test_profile_failure_rolls_back_user_changes(self):
        serializer = CustomerProfileSerializer(self.customer.customer_profile, data={'first_name': 'Changed', 'address': 'Osu'}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with patch.object(CustomerProfile, 'save', side_effect=RuntimeError('Simulated failure')):
            with self.assertRaises(RuntimeError):
                serializer.save()
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, 'Ama')
        self.assertEqual(self.customer.customer_profile.address, 'Accra')

    def test_login_completion_matches_saved_flag(self):
        CustomerProfile.objects.filter(user=self.customer).update(is_complete=False)
        DriverProfile.objects.filter(user=self.driver).update(is_complete=False)
        self.client.force_authenticate(None)
        for user in [self.customer, self.driver]:
            response = self.client.post('/api/v1/auth/login/', {'email': user.email, 'password': 'Profile!Password739'}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertFalse(response.data['profile_complete'])
