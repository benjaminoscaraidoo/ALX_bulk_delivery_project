import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError
from customer.models import CustomUser, DriverProfile
from order.models import Order, Package
from .models import Delivery, DriverRoutePlan
from .routing import collect_stops, current_route, optimize_route, sequence_stops, driving_matrix, RoutingUnavailable


def matrix(addresses):
    return [[(abs(i-j)*60, abs(i-j)*1000) for j in range(len(addresses))] for i in range(len(addresses))]


@override_settings(AUTO_ROUTE_PLANNING=False)
class DriverRoutingTests(TestCase):
    def setUp(self):
        self.customer = CustomUser.objects.create_user('route-customer@example.com', None, role='customer', is_active=True)
        self.user = CustomUser.objects.create_user('route-driver@example.com', None, role='driver', is_active=True)
        self.driver = DriverProfile.objects.get(user=self.user)
        self.order = Order.objects.create(customer_id=self.customer, driver_id=self.driver, order_status='assigned', pickup_address='Pickup A')
        self.package = Package.objects.create(order_id=self.order, delivery_address='Drop A')
        self.delivery = Delivery.objects.create(package_id=self.package, rider=self.driver)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_combines_orders_and_preserves_each_pickup(self):
        order = Order.objects.create(customer_id=self.customer, driver_id=self.driver, order_status='assigned', pickup_address='Pickup B')
        package = Package.objects.create(order_id=order, delivery_address='Drop B')
        Delivery.objects.create(package_id=package, rider=self.driver)
        with patch('delivery.routing.driving_matrix', side_effect=matrix):
            result = optimize_route(self.driver.pk)
        self.assertEqual(len(result['stops']), 4)
        seen = set()
        for stop in result['stops']:
            if stop['requires']:
                self.assertIn(stop['requires'], seen)
            seen.add(stop['key'])
        self.assertEqual(result['stops'][-1]['kind'], 'delivery')

    def test_open_route_does_not_include_return_leg(self):
        with patch('delivery.routing.driving_matrix', side_effect=matrix):
            result = optimize_route(self.driver.pk)
        self.assertEqual(result['duration_seconds'], 120)
        self.assertEqual(result['distance_meters'], 2000)

    def test_already_collected_packages_do_not_need_pickup(self):
        self.delivery.delivery_status = 'picked_up'
        self.delivery.save()
        stops, _ = collect_stops(self.driver.pk)
        self.assertEqual(len(stops), 1)
        self.assertIsNone(stops[0]['requires'])
        with self.assertRaises(ValidationError):
            optimize_route(self.driver.pk)
        with patch('delivery.routing.driving_matrix', side_effect=matrix):
            self.assertEqual(len(optimize_route(self.driver.pk, 'Current location')['stops']), 1)

    def test_incomplete_order_waits_instead_of_partial_route(self):
        Package.objects.create(order_id=self.order, delivery_address='Another address')
        stops, waiting = collect_stops(self.driver.pk)
        self.assertEqual(stops, [])
        self.assertEqual(waiting, 1)

    def test_completed_stops_removed_and_no_other_driver_data(self):
        with patch('delivery.routing.driving_matrix', side_effect=matrix):
            optimize_route(self.driver.pk)
        self.delivery.delivery_status = 'picked_up'
        self.delivery.save()
        result = current_route(self.driver.pk)
        self.assertEqual(len(result['stops']), 1)
        self.assertIsNone(result['distance_meters'])
        self.order.driver_id = None
        self.order.save()
        self.assertEqual(current_route(self.driver.pk)['stops'], [])

    def test_changed_address_requires_refresh(self):
        with patch('delivery.routing.driving_matrix', side_effect=matrix):
            optimize_route(self.driver.pk)
        self.delivery.address = 'New address'
        self.delivery.save()
        result = current_route(self.driver.pk)
        self.assertTrue(result['needs_refresh'])
        self.assertEqual(result['stops'], [])

    def test_snapshot_changed_during_provider_call_not_saved(self):
        def changed(addresses):
            Delivery.objects.filter(pk=self.delivery.pk).update(delivery_status='picked_up')
            return matrix(addresses)
        with patch('delivery.routing.driving_matrix', side_effect=changed), self.assertRaises(ValidationError):
            optimize_route(self.driver.pk)
        self.assertFalse(DriverRoutePlan.objects.exists())

    def test_automatic_refresh_reuses_unchanged_plan(self):
        with patch('delivery.routing.driving_matrix', side_effect=matrix) as provider:
            optimize_route(self.driver.pk, force=False)
            optimize_route(self.driver.pk, force=False)
        self.assertEqual(provider.call_count, 1)

    @override_settings(AUTO_ROUTE_PLANNING=True)
    def test_delivery_creation_automatically_plans_after_commit(self):
        self.delivery.delete()
        with patch('delivery.routing.driving_matrix', side_effect=matrix) as provider:
            with self.captureOnCommitCallbacks(execute=True):
                Delivery.objects.create(package_id=self.package, rider=self.driver)
        self.assertEqual(provider.call_count, 1)
        self.assertTrue(DriverRoutePlan.objects.filter(driver=self.driver).exists())

    @override_settings(AUTO_ROUTE_PLANNING=True)
    def test_mapping_failure_keeps_delivery(self):
        self.delivery.delete()
        with patch('delivery.routing.driving_matrix', side_effect=RoutingUnavailable()):
            with self.captureOnCommitCallbacks(execute=True):
                delivery = Delivery.objects.create(package_id=self.package, rider=self.driver)
        self.assertTrue(Delivery.objects.filter(pk=delivery.pk).exists())

    def test_api_customer_rejected_and_driver_only_sees_own_route(self):
        self.client.force_authenticate(self.customer)
        self.assertEqual(self.client.get('/api/v1/driver/route/').status_code, 403)
        self.assertEqual(self.client.post('/api/v1/driver/route/optimize/', {}).status_code, 403)
        self.client.force_authenticate(self.user)
        with patch('delivery.routing.driving_matrix', side_effect=matrix):
            self.assertEqual(self.client.post('/api/v1/driver/route/optimize/', {}, format='json').status_code, 200)
        self.assertEqual(len(self.client.get('/api/v1/driver/route/').data['stops']), 2)
        other = CustomUser.objects.create_user('other-route-driver@example.com', None, role='driver', is_active=True)
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get('/api/v1/driver/route/').data['stops'], [])

    def test_provider_failure_preserves_existing_plan(self):
        with patch('delivery.routing.driving_matrix', side_effect=matrix):
            optimize_route(self.driver.pk)
        old = DriverRoutePlan.objects.get(driver=self.driver).stops
        with patch('delivery.routing.driving_matrix', side_effect=RoutingUnavailable()), self.assertRaises(RoutingUnavailable):
            optimize_route(self.driver.pk, 'Changed start')
        self.assertEqual(DriverRoutePlan.objects.get(driver=self.driver).stops, old)

    def test_route_limit_is_explicit(self):
        with patch('delivery.routing.collect_stops', return_value=([{}]*25, 0)), self.assertRaises(ValidationError):
            optimize_route(self.driver.pk)

    def test_dashboard_displays_route(self):
        with patch('delivery.routing.driving_matrix', side_effect=matrix):
            optimize_route(self.driver.pk)
        self.client.force_login(self.user)
        response = self.client.get('/')
        self.assertContains(response, 'Your delivery route')
        self.assertContains(response, 'Pickup A')
        self.assertContains(response, 'Drop A')


@override_settings(GOOGLE_MAPS_API_KEY='test-key')
class MatrixTests(TestCase):
    def response(self, entries):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(entries).encode()
        return response

    def test_google_payload_and_field_mask(self):
        entries = [dict(originIndex=i, destinationIndex=j, condition='ROUTE_EXISTS', duration='3.5s', distanceMeters=12) for i in range(2) for j in range(2)]
        with patch('delivery.routing.urlopen', return_value=self.response(entries)) as send:
            result = driving_matrix(['A', 'B'])
        self.assertEqual(result[0][1], (3.5, 12))
        request = send.call_args.args[0]
        self.assertEqual(json.loads(request.data)['travelMode'], 'DRIVE')
        self.assertIn('condition', request.get_header('X-goog-fieldmask'))

    def test_missing_or_unreachable_or_invalid_matrix_rejected(self):
        for entries in [[], [dict(condition='ROUTE_NOT_FOUND')], [dict(condition='ROUTE_EXISTS', duration='NaNs')]]:
            with self.subTest(entries=entries), patch('delivery.routing.urlopen', return_value=self.response(entries)), self.assertRaises(RoutingUnavailable):
                driving_matrix(['A'])

    def test_greedy_does_not_deliver_before_pickup_even_when_closer(self):
        stops = [dict(key='pickup', requires=None), dict(key='drop', requires='pickup')]
        route, seconds, _ = sequence_stops(stops, [[(0,0),(100,1),(1,1)],[(100,1),(0,0),(2,1)],[(1,1),(2,1),(0,0)]])
        self.assertEqual([s['key'] for s in route], ['pickup', 'drop'])
        self.assertEqual(seconds, 102)
