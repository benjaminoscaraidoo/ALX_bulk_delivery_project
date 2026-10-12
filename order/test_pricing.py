from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase
from customer.models import CustomUser, CustomerProfile, DriverProfile
from delivery.models import Delivery, Payment
from order.models import Order, Package, DistanceTariff, DeliveryArea
from order.pricing import driving_distance, RoutingUnavailable


class PricingPaymentTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.customer = CustomUser.objects.create_user('buyer@example.com', None, role='customer', is_active=True)
        self.other = CustomUser.objects.create_user('other@example.com', None, role='customer', is_active=True)
        self.admin = CustomUser.objects.create_user('admin@example.com', None, role='admin', is_active=True, is_staff=True)
        self.driver = CustomUser.objects.create_user('driver@example.com', None, role='driver', is_active=True)
        self.order = Order.objects.create(customer_id=self.customer, driver_id=DriverProfile.objects.get(user=self.driver), pickup_address='Accra Mall', order_status='assigned')
        self.package = Package.objects.create(order_id=self.order, delivery_address='Osu, Accra')
        Delivery.objects.create(package_id=self.package, rider=self.order.driver_id)
        self.client.force_authenticate(self.customer)

    def quote(self, meters=10000, **data):
        with patch('order.pricing.driving_distance', return_value=meters):
            return self.client.post('/api/v1/package/quote/', {'package_id': self.package.pk, **data}, format='json')

    def payment(self, method='cash', **data):
        return self.client.post('/api/v1/payment/create/', {'package_id': self.package.pk, 'payment_method': method, **data}, format='json')

    def confirm(self, payment, **data):
        return self.client.post(f'/api/v1/payment/{payment.pk}/confirm/', data, format='json')

    def test_exact_bracket_boundaries(self):
        for meters, charge in [(0, '35.00'), (10000, '35.00'), (10001, '50.00'), (25000, '50.00'), (25001, '60.00'), (30000, '60.00')]:
            with self.subTest(meters=meters):
                self.package = Package.objects.create(order_id=self.order, delivery_address='Osu')
                response = self.quote(meters)
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data['amount'], charge)

    def test_above_thirty_requires_admin_quote(self):
        response = self.quote(30001)
        self.assertTrue(response.data['quote_required'])
        self.assertEqual(self.quote(30001, amount='75', reason='Long route').status_code, 400)
        self.client.force_authenticate(self.admin)
        response = self.quote(30001, amount='75', reason='Long route')
        self.assertEqual(response.data['amount'], '75.00')

    def test_tariff_changes_do_not_change_stored_quotes(self):
        self.quote()
        DistanceTariff.objects.filter(upper_km=10).update(charge=99)
        response = self.quote()
        self.assertEqual(response.data['amount'], '35.00')
        self.order.refresh_from_db()
        self.assertEqual(self.order.total_price, Decimal('35'))

    def test_outside_accra_area_price(self):
        area = DeliveryArea.objects.get(name='Kumasi')
        area.charge = Decimal('120')
        area.save()
        self.package.outside_accra = True
        self.package.delivery_area = area
        self.package.save()
        response = self.quote()
        self.assertEqual(response.data['amount'], '120.00')
        self.assertEqual(response.data['area_name'], 'Kumasi')

    def test_unpriced_area_requires_quote(self):
        self.package.outside_accra = True
        self.package.delivery_area = DeliveryArea.objects.get(name='Tamale')
        self.package.save()
        self.assertTrue(self.quote().data['quote_required'])

    def test_customer_cannot_quote_another_customers_package(self):
        self.client.force_authenticate(self.other)
        self.assertEqual(self.quote().status_code, 400)

    def test_payment_requires_quote(self):
        self.assertEqual(self.payment().status_code, 400)

    def test_payment_uses_quote_and_ignores_forged_fields(self):
        self.quote()
        response = self.payment(amount='1', payment_status='paid', paid_at='2026-01-01')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['amount'], '35.00')
        self.assertEqual(response.data['payment_status'], 'pending')
        self.assertEqual(self.payment().status_code, 400)

    def test_only_assigned_driver_confirms_cash(self):
        self.quote()
        self.payment()
        payment = Payment.objects.get(package_id=self.package)
        self.assertEqual(self.confirm(payment).status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.confirm(payment).status_code, 403)
        self.client.force_authenticate(self.driver)
        self.assertEqual(self.confirm(payment).status_code, 200)
        self.assertEqual(self.confirm(payment).status_code, 400)

    def test_mobile_money_requires_admin_and_reference(self):
        self.quote()
        self.payment('mobile_money')
        payment = Payment.objects.get(package_id=self.package)
        self.client.force_authenticate(self.driver)
        self.assertEqual(self.confirm(payment, transaction_reference='MM123').status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.confirm(payment).status_code, 400)
        self.assertEqual(self.confirm(payment, transaction_reference='MM123').status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.confirmed_by, self.admin)

    def test_other_customer_cannot_create_or_see_payment(self):
        self.quote()
        self.payment()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.payment().status_code, 403)
        self.assertEqual(self.client.get('/api/v1/search/payment/').data['count'], 0)

    def test_google_failure_returns_503_without_quote(self):
        with patch('order.pricing.driving_distance', side_effect=RoutingUnavailable()):
            response = self.client.post('/api/v1/package/quote/', {'package_id': self.package.pk}, format='json')
        self.assertEqual(response.status_code, 503)
        self.assertFalse(hasattr(self.package, 'quote'))

    @override_settings(GOOGLE_MAPS_API_KEY='test-key')
    def test_google_request_uses_drive_and_distance_mask(self):
        response = MagicMock()
        response.read.return_value = b'{"routes":[{"distanceMeters":12345}]}'
        response.__enter__.return_value = response
        with patch('order.pricing.urlopen', return_value=response) as mock:
            self.assertEqual(driving_distance('Accra Mall', 'Osu'), 12345)
        request = mock.call_args.args[0]
        import json
        self.assertEqual(json.loads(request.data)['travelMode'], 'DRIVE')
        self.assertEqual(request.get_header('X-goog-fieldmask'), 'routes.distanceMeters')

    def record_reference(self, payment, reference='MOMO-12345'):
        return self.client.post(f'/api/v1/payment/{payment.pk}/reference/', {'transaction_reference': reference}, format='json')

    def test_driver_records_momo_id_without_confirming_payment(self):
        self.quote()
        self.payment('mobile_money')
        payment = Payment.objects.get(package_id=self.package)
        self.client.force_authenticate(self.driver)
        response = self.record_reference(payment)
        self.assertEqual(response.status_code, 200, response.data)
        payment.refresh_from_db()
        self.assertEqual(payment.transaction_reference, 'MOMO-12345')
        self.assertEqual(payment.transaction_recorded_by, self.driver)
        self.assertIsNotNone(payment.transaction_recorded_at)
        self.assertEqual(payment.payment_status, 'pending')
        self.assertIsNone(payment.confirmed_by)
        self.assertEqual(self.confirm(payment).status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.confirm(payment).status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.payment_status, 'paid')
        self.assertEqual(payment.transaction_recorded_by, self.driver)
        self.assertEqual(payment.confirmed_by, self.admin)
        self.assertEqual(self.record_reference(payment, 'CHANGED').status_code, 400)

    def test_admin_can_record_momo_id(self):
        self.quote()
        self.payment('mobile_money')
        payment = Payment.objects.get(package_id=self.package)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.record_reference(payment).status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.transaction_recorded_by, self.admin)
        self.assertEqual(payment.payment_status, 'pending')

    def test_customer_and_unassigned_driver_cannot_record_momo_id(self):
        self.quote()
        self.payment('mobile_money')
        payment = Payment.objects.get(package_id=self.package)
        self.assertEqual(self.record_reference(payment).status_code, 403)
        stranger = CustomUser.objects.create_user('stranger-driver@example.com', None, role='driver', is_active=True)
        self.client.force_authenticate(stranger)
        self.assertEqual(self.record_reference(payment).status_code, 403)
        payment.refresh_from_db()
        self.assertEqual(payment.transaction_reference, '')

    def test_reference_capture_rejects_cash_and_blank_ids(self):
        self.quote()
        self.payment()
        payment = Payment.objects.get(package_id=self.package)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.record_reference(payment).status_code, 400)
        self.assertEqual(self.record_reference(payment, '   ').status_code, 400)
