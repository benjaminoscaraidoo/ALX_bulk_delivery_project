from unittest.mock import patch

from django.core.cache import cache
from rest_framework.test import APITestCase
from customer.models import CustomUser, CustomerProfile, DriverProfile
from order.models import Order
from delivery.models import Payment


class CompleteOrderWorkflowTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.password = 'Workflow!Password739'
        self.customer = CustomUser.objects.create_user(
            'workflow-customer@example.com', None, password=self.password,
            role='customer', is_active=True,
        )
        CustomerProfile.objects.filter(user=self.customer).update(
            customer_name='Test Customer', address='Accra', is_complete=True,
        )
        self.driver = CustomUser.objects.create_user(
            'workflow-driver@example.com', None, password=self.password,
            role='driver', is_active=True,
        )
        DriverProfile.objects.filter(user=self.driver).update(
            vehicle_type='Motorbike', is_complete=True,
            approval_status='approved', is_approved=True,
        )
        self.admin = CustomUser.objects.create_superuser(
            'workflow-admin@example.com', None, password=self.password,
        )

    def login(self, user):
        cache.clear()
        self.client.credentials()
        response = self.client.post('/api/v1/auth/login/', {
            'email': user.email, 'password': self.password,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + response.data['access'])

    def post(self, path, data, expected):
        # Keep unrelated request throttling out of the workflow assertion.
        cache.clear()
        response = self.client.post(path, data, format='json')
        self.assertEqual(response.status_code, expected, response.data)
        return response.data

    def put(self, path, data, expected):
        cache.clear()
        response = self.client.put(path, data, format='json')
        self.assertEqual(response.status_code, expected, response.data)
        return response.data

    def test_order_to_delivery_and_both_payment_confirmations(self):
        self.login(self.customer)
        result = self.post('/api/v1/order/create/', {'pickup_address': 'Accra Mall, Accra, Ghana'}, 201)
        order_id = result['id']
        self.assertEqual(result['order_status'], 'assigned')
        package_data = {
            'description': 'Test parcel', 'receiver_name': 'Test Recipient',
            'receiver_phone': '+233240000000', 'value': '100.00',
            'delivery_address': 'Osu Oxford Street, Accra, Ghana',
        }
        result = self.post('/api/v1/package/create/', {
            'order_id': order_id, 'packages': [package_data, package_data],
        }, 201)
        packages = result['package_ids']
        for package_id in packages:
            with patch('order.pricing.driving_distance', return_value=9592):
                quote = self.post('/api/v1/package/quote/', {'package_id': package_id}, 200)
            self.assertEqual(quote['amount'], '35.00')
        order = Order.objects.get(pk=order_id)
        self.assertEqual(str(order.total_price), '70.00')
        self.post('/api/v1/delivery/create/', {
            'deliveries': [{'package_id': pk} for pk in packages],
        }, 201)
        cash = self.post('/api/v1/payment/create/', {
            'package_id': packages[0], 'payment_method': 'cash',
        }, 201)
        mobile = self.post('/api/v1/payment/create/', {
            'package_id': packages[1], 'payment_method': 'mobile_money',
        }, 201)
        self.post(f"/api/v1/payment/{cash['id']}/confirm/", {}, 403)
        self.login(self.driver)
        self.put('/api/v1/order/update/', {'order_id': order_id, 'status': 'picked_up'}, 200)
        order.refresh_from_db()
        self.assertEqual(order.order_status, 'in_transit')
        for index, package_id in enumerate(packages):
            self.put('/api/v1/delivery/update/', {
                'package_id': package_id, 'delivery_status': 'delivered', 'received_by': 'Test recipient',
            }, 201)
            order.refresh_from_db()
            self.assertEqual(order.order_status, 'in_transit' if index == 0 else 'delivered')
        self.post(f"/api/v1/payment/{cash['id']}/confirm/", {}, 200)
        self.post(f"/api/v1/payment/{mobile['id']}/confirm/", {'transaction_reference': 'WORKFLOW-MM-001'}, 403)
        self.login(self.admin)
        self.post(f"/api/v1/payment/{mobile['id']}/confirm/", {'transaction_reference': 'WORKFLOW-MM-001'}, 200)
        self.assertEqual(Payment.objects.filter(package_id__order_id=order, payment_status='paid').count(), 2)
        self.assertEqual(Payment.objects.get(pk=cash['id']).confirmed_by, self.driver)
        self.assertEqual(Payment.objects.get(pk=mobile['id']).confirmed_by, self.admin)
        self.login(self.customer)
        response = self.client.get('/api/v1/search/order/')
        self.assertEqual(response.status_code, 200, response.data)
        summary = next(item for item in response.data['results'] if item['id'] == order_id)
        self.assertTrue(summary['pricing_complete'])
        self.assertEqual(summary['total_price'], '70.00')
