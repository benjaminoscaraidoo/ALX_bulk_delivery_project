import csv
import io
from datetime import datetime, date, timezone as dt_timezone
from decimal import Decimal
from django.test import override_settings
from django.core.cache import cache
from rest_framework.test import APITestCase
from customer.models import CustomUser, DriverProfile
from order.models import Order, Package, DeliveryQuote
from delivery.models import Delivery, DeliveryEvent, Payment
from frontend.reports import driver_workloads, period_data


@override_settings(AUTO_ROUTE_PLANNING=False, NOTIFICATION_SEND_IMMEDIATELY=False)
class ReportTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.staff = CustomUser.objects.create_user('reports-admin@example.com', None, role='admin', is_staff=True, is_active=True)
        self.customer = CustomUser.objects.create_user('reports-customer@example.com', None, role='customer', is_active=True)
        self.driver = CustomUser.objects.create_user('reports-driver@example.com', None, role='driver', is_active=True)
        self.profile = DriverProfile.objects.get(user=self.driver)
        self.order = Order.objects.create(customer_id=self.customer, driver_id=self.profile, pickup_address='Pickup', created_at=date(2026, 10, 1), order_status='in_transit')
        self.package = Package.objects.create(order_id=self.order, delivery_address='Drop')
        self.client.force_login(self.staff)
        self.dates = {'start': '2026-10-01', 'end': '2026-10-13'}

    def payment(self, amount, status='paid', method='cash', paid_at=date(2026, 10, 13), package=None):
        package = package or Package.objects.create(order_id=self.order)
        return Payment.objects.create(package_id=package, amount=amount, payment_method=method, payment_status=status, paid_at=paid_at if status=='paid' else None)

    def delivery(self, status='delivered', when=None, package=None):
        package = package or self.package
        return Delivery.objects.create(package_id=package, rider=self.profile, delivery_status=status, delivered_at=when if status=='delivered' else None, returned_at=when if status=='returned' else None, received_by='Recipient')

    def test_staff_can_view_and_nonstaff_cannot_view_or_export(self):
        self.assertEqual(self.client.get('/reports/', self.dates).status_code, 200)
        for user in [self.customer, self.driver]:
            self.client.force_login(user)
            for kind in ['', 'deliveries', 'payments', 'workloads', 'outstanding', 'failures', 'unrecorded']:
                self.assertEqual(self.client.get('/reports/', dict(self.dates, export=kind)).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get('/reports/').status_code, 302)

    def test_period_uses_completion_date_not_order_creation(self):
        self.order.created_at = date(2026, 9, 1)
        self.order.save()
        self.delivery(when=datetime(2026, 10, 13, 23, 59, tzinfo=dt_timezone.utc))
        self.delivery(when=datetime(2026, 10, 14, 0, 0, tzinfo=dt_timezone.utc), package=Package.objects.create(order_id=self.order))
        data = period_data(date(2026, 10, 1), date(2026, 10, 13))
        self.assertEqual(data['orders_created'], 0)
        self.assertEqual(data['delivered_count'], 1)

    def test_payment_totals_exclude_pending_and_outside_period(self):
        self.payment('35.00')
        self.payment('50.00', method='mobile_money')
        self.payment('60.00', status='pending')
        self.payment('100.00', paid_at=date(2026, 9, 30))
        data = period_data(date(2026, 10, 1), date(2026, 10, 13))
        self.assertEqual(data['confirmed_amount'], Decimal('85.00'))
        self.assertEqual(data['method_totals'][0]['amount'], Decimal('35.00'))
        self.assertEqual(data['method_totals'][1]['amount'], Decimal('50.00'))

    def test_backlog_is_current_even_with_old_activity_range(self):
        self.payment('35.00', status='pending')
        cancelled = Order.objects.create(customer_id=self.customer, order_status='cancelled')
        self.payment('90.00', status='pending', package=Package.objects.create(order_id=cancelled))
        quoted = Package.objects.create(order_id=self.order)
        DeliveryQuote.objects.create(package=quoted, amount=60, pickup_address='Pickup', delivery_address='Drop', outside_accra=False, reason='Test')
        response = self.client.get('/reports/', {'start': '2020-01-01', 'end': '2020-01-02'})
        self.assertEqual(response.context['confirmed_amount'], Decimal('0.00'))
        self.assertEqual(response.context['unpaid_amount'], Decimal('35.00'))
        self.assertEqual(response.context['missing_payment_amount'], Decimal('60.00'))

    def test_driver_counts_do_not_multiply_from_joins(self):
        self.delivery(status='picked_up')
        self.delivery(status='failed', package=Package.objects.create(order_id=self.order))
        second = Order.objects.create(customer_id=self.customer, driver_id=self.profile, order_status='assigned')
        self.delivery(status='assigned', package=Package.objects.create(order_id=second))
        self.delivery(status='assigned', package=Package.objects.create(order_id=second))
        self.delivery(status='returning', package=Package.objects.create(order_id=second))
        closed = Order.objects.create(customer_id=self.customer, driver_id=self.profile, order_status='cancelled')
        self.delivery(status='assigned', package=Package.objects.create(order_id=closed))
        workload = driver_workloads().get(pk=self.profile.pk)
        self.assertEqual(workload.active_order_count, 2)
        self.assertEqual(workload.awaiting_pickup, 2)
        self.assertEqual(workload.on_board, 1)
        self.assertEqual(workload.failed, 1)
        self.assertEqual(workload.returning, 1)

    def test_failed_attempt_count_is_not_unresolved_package_count(self):
        delivery = self.delivery(status='picked_up')
        for action in ['failed', 'retry', 'failed', 'retry']:
            event = DeliveryEvent.objects.create(delivery=delivery, action=action, actor=self.driver)
            DeliveryEvent.objects.filter(pk=event.pk).update(created_at=datetime(2026, 10, 12, tzinfo=dt_timezone.utc))
        response = self.client.get('/reports/', self.dates)
        self.assertEqual(response.context['failed_attempts'], 2)
        self.assertEqual(response.context['failed_count'], 0)

    def test_returned_packages_not_counted_as_delivered(self):
        self.delivery(status='returned', when=datetime(2026, 10, 12, tzinfo=dt_timezone.utc))
        data = period_data(date(2026, 10, 1), date(2026, 10, 13))
        self.assertEqual(data['returned_count'], 1)
        self.assertEqual(data['delivered_count'], 0)

    def test_invalid_dates_or_exports_return_clear_error(self):
        for params in [dict(start='bad', end='2026-10-13'), dict(start='2026-10-14', end='2026-10-13'), dict(self.dates, export='secret')]:
            self.assertEqual(self.client.get('/reports/', params).status_code, 400)

    def test_csv_uses_same_dates_and_escapes_formula_cells(self):
        delivery = self.delivery(when=datetime(2026, 10, 12, tzinfo=dt_timezone.utc))
        delivery.received_by = '=DANGEROUS()'
        delivery.save()
        response = self.client.get('/reports/', dict(self.dates, export='deliveries'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        rows = list(csv.reader(io.StringIO(b''.join(response.streaming_content).decode())))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][3], "'=DANGEROUS()")

    def test_payment_csv_and_workload_export(self):
        self.payment('35.00')
        for kind, text in [('payments', '35.00'), ('workloads', 'reports-driver@example.com')]:
            response = self.client.get('/reports/', dict(self.dates, export=kind))
            content = b''.join(response.streaming_content).decode()
            self.assertIn(text, content)

    def test_empty_report_shows_zero_and_no_completion_date_warning(self):
        response = self.client.get('/reports/', self.dates)
        self.assertContains(response, 'No completed deliveries in this period.')
        self.assertEqual(response.context['confirmed_amount'], Decimal('0.00'))
        self.delivery()
        response = self.client.get('/reports/', self.dates)
        self.assertContains(response, 'no recorded completion date')
        self.assertEqual(response.context['delivered_count'], 0)


    def test_outstanding_and_failures_exports_include_current_records(self):
        self.payment('60.00', status='pending')
        self.delivery(status='failed')
        for kind, value in [('outstanding', '60.00'), ('failures', self.package.pk)]:
            response = self.client.get('/reports/', {'start': '2020-01-01', 'end': '2020-01-02', 'export': kind})
            self.assertIn('current.csv', response['Content-Disposition'])
            self.assertIn(value, b''.join(response.streaming_content).decode())
