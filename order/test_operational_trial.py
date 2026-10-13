"""Isolated three-order operational trial; Google, email and SMS are mocked."""
from unittest.mock import patch
from decimal import Decimal
from django.test import override_settings
from django.core.cache import cache
from django.core.management import call_command
import io
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from customer.models import CustomUser, CustomerProfile, DriverProfile
from order.models import Order
from delivery.models import Delivery
from notifications.models import Notification, NotificationSend


@override_settings(AUTO_ROUTE_PLANNING=False, NOTIFICATION_SEND_IMMEDIATELY=False, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class OperationalTrialTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.password = 'Operational!Trial2026'
        self.customer = CustomUser.objects.create_user('trial-customer@example.com', '+233241234561', password=self.password, role='customer', is_active=True, first_name='Trial', last_name='Customer')
        CustomerProfile.objects.filter(user=self.customer).update(customer_name='Trial Customer', address='Accra', is_complete=True)
        self.driver = CustomUser.objects.create_user('trial-driver@example.com', '+233241234562', password=self.password, role='driver', is_active=True, first_name='Trial', last_name='Driver')
        DriverProfile.objects.filter(user=self.driver).update(vehicle_type='Van', vehicle_number='TEST-001', license_number='TEST-LIC', is_complete=True, approval_status='approved', is_approved=True)
        self.admin = CustomUser.objects.create_superuser('trial-admin@example.com', '+233241234563', password=self.password)
        self.clients = {}
        for user in [self.customer, self.driver, self.admin]:
            client = APIClient()
            response = client.post('/api/v1/auth/login/', {'identifier': user.email, 'password': self.password}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            client.credentials(HTTP_AUTHORIZATION='Bearer '+response.data['access'])
            self.clients[user.pk] = client

    def request(self, user, path, data, expected=200, method='post'):
        response = getattr(self.clients[user.pk], method)(path, data, format='json')
        self.assertEqual(response.status_code, expected, (path, response.data))
        return response.data

    def test_three_orders_route_retry_return_payment_inbox_and_reports(self):
        pickups = ['Ofankor Barrier, Accra', 'Atomic Hills Pharmacy, Kwabenya', 'Sowutuom, Accra']
        destinations = [
            ['Christ Oilfields Authority Church', 'Korle Bu Teaching Hospital', 'Mallam Market, Sakaman', 'Kaneshie Market'],
            ['Madina', '37 Military Hospital', 'Ofankor Barrier', 'Tema Community 22', 'Accra Mall', 'Mamprobi Polyclinic'],
            ['Asofa Cemetery', 'Spintex Manet Junction', 'VIP Station Circle', 'Tudu'],
        ]
        orders, packages, payments = [], [], {}
        for pickup, drops in zip(pickups, destinations):
            result = self.request(self.customer, '/api/v1/order/create/', {'pickup_address': pickup}, 201)
            order_id = result['id']; orders.append(order_id)
            result = self.request(self.customer, '/api/v1/package/create/', {'order_id': order_id, 'packages': [dict(description='Trial parcel', receiver_name='Recipient', receiver_phone='+233241234564', delivery_address=address) for address in drops]}, 201)
            ids = result['package_ids']; packages.extend(ids)
            for package_id in ids:
                with patch('order.pricing.driving_distance', return_value=9000):
                    self.request(self.customer, '/api/v1/package/quote/', {'package_id': package_id})
                method = 'cash' if len(payments)%2 == 0 else 'mobile_money'
                payments[package_id] = self.request(self.customer, '/api/v1/payment/create/', {'package_id': package_id, 'payment_method': method}, 201)
            self.request(self.customer, '/api/v1/delivery/create/', {'deliveries': [{'package_id': pk} for pk in ids]}, 201)
        self.assertEqual(len(packages), 14)
        with patch('delivery.routing.driving_matrix', side_effect=lambda addresses: [[(abs(i-j)*60, abs(i-j)*1000) for j in range(len(addresses))] for i in range(len(addresses))]):
            route = self.request(self.driver, '/api/v1/driver/route/optimize/', {'starting_address': pickups[0]})
        self.assertEqual(len(route['stops']), 17)
        seen = set()
        for stop in route['stops']:
            if stop['requires']:
                self.assertIn(stop['requires'], seen)
            seen.add(stop['key'])
        self.assertEqual(len(seen), 17)
        for order in orders:
            self.request(self.driver, '/api/v1/order/update/', {'order_id': order, 'status': 'picked_up'}, method='put')
        retried, returned = packages[0], packages[-1]
        for package in [retried, returned]:
            self.request(self.driver, '/api/v1/delivery/update/', {'package_id': package, 'delivery_status': 'failed', 'failure_reason': 'receiver_unavailable'}, 201, 'put')
        self.request(self.admin, f'/api/v1/delivery/{Delivery.objects.get(package_id=retried).pk}/resolution/', {'action': 'retry', 'reason': 'Receiver available now'})
        self.request(self.admin, f'/api/v1/delivery/{Delivery.objects.get(package_id=returned).pk}/resolution/', {'action': 'return', 'reason': 'Sender requested return'})
        with patch('delivery.routing.driving_matrix', side_effect=lambda addresses: [[(abs(i-j)*60, abs(i-j)*1000) for j in range(len(addresses))] for i in range(len(addresses))]):
            remaining_route = self.request(self.driver, '/api/v1/driver/route/optimize/', {'starting_address': 'Trial current location'})
        self.assertEqual(len(remaining_route['stops']), 14)
        self.assertEqual([stop['address'] for stop in remaining_route['stops'] if stop['kind'] == 'return'], [pickups[-1]])
        for package in packages:
            self.request(self.driver, '/api/v1/delivery/update/', {'package_id': package, 'delivery_status': 'returned' if package == returned else 'delivered', 'received_by': 'Sender' if package == returned else 'Actual recipient'}, 201, 'put')
            if package != returned:
                payment = payments[package]
                confirmer = self.driver if payment['payment_method'] == 'cash' else self.admin
                self.request(confirmer, f"/api/v1/payment/{payment['id']}/confirm/", {'transaction_reference': f'TRIAL-{package}'} if confirmer == self.admin else {})
        self.assertEqual(Delivery.objects.filter(package_id__order_id_id__in=orders, delivery_status='delivered').count(), 13)
        self.assertEqual(Order.objects.get(pk=orders[-1]).order_status, 'completed_returns')
        inbox = self.clients[self.customer.pk].get('/api/v1/notifications/')
        self.assertEqual(inbox.status_code, 200)
        self.assertEqual(inbox.data['count'], 34)
        self.assertEqual(Notification.objects.filter(customer=self.customer).count(), 34)
        with patch('notifications.services.check_sms_configuration'), patch('notifications.services.send_sms') as sms, patch('notifications.services.send_mail', return_value=1) as email:
            call_command('send_notifications', stdout=io.StringIO())
        self.assertEqual(sms.call_count, 34)
        self.assertEqual(email.call_count, 34)
        self.assertEqual(NotificationSend.objects.filter(status='sent').count(), 68)
        admin = self.clients[self.admin.pk]
        response = admin.post('/login/', {'username': self.admin.email, 'password': self.password})
        self.assertEqual(response.status_code, 302)
        today = timezone.localdate().isoformat()
        report = admin.get('/reports/', {'start': today, 'end': today})
        self.assertEqual(report.status_code, 200)
        self.assertEqual(report.context['delivered_count'], 13)
        self.assertEqual(report.context['returned_count'], 1)
        self.assertEqual(report.context['failed_attempts'], 2)
        self.assertEqual(report.context['confirmed_amount'], Decimal('455.00'))
        self.assertEqual(report.context['unpaid_amount'], Decimal('35.00'))
        self.assertEqual(report.context['failed_count'], 0)
