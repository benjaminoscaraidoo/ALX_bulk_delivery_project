"""Staff reports: dated activity and a separately labelled current backlog."""
import csv
from datetime import timedelta
from decimal import Decimal
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Sum
from django.http import StreamingHttpResponse
from django.shortcuts import render
from django.utils import timezone
from customer.models import DriverProfile
from delivery.models import Delivery, DeliveryEvent, Payment
from order.models import Order, Package
from order.services import ACTIVE_ORDER_STATUSES


class ReportDates(forms.Form):
    start = forms.DateField(label='From', widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(label='To', widget=forms.DateInput(attrs={'type': 'date'}))

    def clean(self):
        data = super().clean()
        if data.get('start') and data.get('end') and data['start'] > data['end']:
            raise forms.ValidationError('The start date must be on or before the end date.')
        return data


def driver_workloads():
    return DriverProfile.objects.filter(user__role='driver').select_related('user').annotate(
        active_order_count=Count('dorders', filter=Q(dorders__order_status__in=ACTIVE_ORDER_STATUSES), distinct=True),
        awaiting_pickup=Count('assigned_deliveries', filter=Q(assigned_deliveries__delivery_status='assigned', assigned_deliveries__package_id__order_id__order_status__in=ACTIVE_ORDER_STATUSES), distinct=True),
        on_board=Count('assigned_deliveries', filter=Q(assigned_deliveries__delivery_status='picked_up', assigned_deliveries__package_id__order_id__order_status__in=ACTIVE_ORDER_STATUSES), distinct=True),
        failed=Count('assigned_deliveries', filter=Q(assigned_deliveries__delivery_status='failed', assigned_deliveries__package_id__order_id__order_status__in=ACTIVE_ORDER_STATUSES), distinct=True),
        returning=Count('assigned_deliveries', filter=Q(assigned_deliveries__delivery_status='returning', assigned_deliveries__package_id__order_id__order_status__in=ACTIVE_ORDER_STATUSES), distinct=True),
    ).order_by('-active_order_count', 'pk')


def period_data(start, end):
    delivered = Delivery.objects.filter(delivery_status='delivered', delivered_at__date__range=(start, end)).select_related('package_id__order_id', 'rider__user').order_by('-delivered_at', 'pk')
    paid = Payment.objects.filter(payment_status='paid', paid_at__range=(start, end)).select_related('package_id__order_id', 'confirmed_by').order_by('-paid_at', 'pk')
    money = paid.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    method_totals = [dict(method=label, count=paid.filter(payment_method=value).count(), amount=paid.filter(payment_method=value).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')) for value, label in Payment.Method.choices]
    return dict(delivered=delivered, paid=paid, confirmed_amount=money, method_totals=method_totals,
                orders_created=Order.objects.filter(created_at__range=(start, end)).count(),
                delivered_count=delivered.count(),
                failed_attempts=DeliveryEvent.objects.filter(action='failed', created_at__date__range=(start, end)).count(),
                returned_count=Delivery.objects.filter(delivery_status='returned', returned_at__date__range=(start, end)).count())


def outstanding_payments():
    return Payment.objects.exclude(package_id__order_id__order_status='cancelled').filter(payment_status__in=['pending', 'failed'])


def quoted_without_payment():
    return Package.objects.exclude(order_id__order_status='cancelled').filter(quote__isnull=False, payment__isnull=True)


def unresolved_failures():
    return Delivery.objects.filter(delivery_status='failed', package_id__order_id__order_status__in=ACTIVE_ORDER_STATUSES)


class Echo:
    def write(self, value):
        return value


def safe_cell(value):
    text = '' if value is None else str(value)
    if text.lstrip().startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')):
        return "'" + text
    return text


def export_csv(kind, data, start, end):
    def rows():
        if kind == 'deliveries':
            yield ['Package', 'Order', 'Delivered at UTC', 'Received by', 'Driver']
            for d in data['delivered'].iterator(chunk_size=500):
                yield [d.package_id_id, d.package_id.order_id_id, d.delivered_at.isoformat(), d.received_by, (d.rider.user.get_full_name() or d.rider.user.phone_number or d.rider.user.email) if d.rider else 'Unassigned']
        elif kind == 'payments':
            yield ['Payment', 'Package', 'Order', 'Method', 'Confirmed amount GHS', 'Confirmed date', 'Confirmed by']
            for p in data['paid'].iterator(chunk_size=500):
                yield [p.pk, p.package_id_id, p.package_id.order_id_id, p.get_payment_method_display(), f'{p.amount:.2f}', p.paid_at, p.confirmed_by.get_full_name() or p.confirmed_by.email or p.confirmed_by.phone_number if p.confirmed_by else 'Not recorded']
        elif kind == 'outstanding':
            yield ['Payment', 'Package', 'Order', 'Method', 'Payment status', 'Amount GHS']
            for p in outstanding_payments().select_related('package_id__order_id').order_by('pk').iterator(chunk_size=500):
                yield [p.pk, p.package_id_id, p.package_id.order_id_id, p.get_payment_method_display(), p.get_payment_status_display(), f'{p.amount:.2f}']
        elif kind == 'unrecorded':
            yield ['Package', 'Order', 'Quoted amount GHS']
            for package in quoted_without_payment().select_related('quote', 'order_id').order_by('pk').iterator(chunk_size=500):
                yield [package.pk, package.order_id_id, f'{package.quote.amount:.2f}']
        elif kind == 'failures':
            yield ['Package', 'Order', 'Reason', 'Notes', 'Attempts', 'Driver']
            for d in unresolved_failures().select_related('package_id__order_id', 'rider__user').order_by('pk').iterator(chunk_size=500):
                yield [d.package_id_id, d.package_id.order_id_id, d.failure_reason, d.delivery_notes, d.attempt_count, (d.rider.user.get_full_name() or d.rider.user.phone_number or d.rider.user.email) if d.rider else 'Unassigned']
        else:
            yield ['Driver', 'Phone', 'Approval', 'Available', 'Account active', 'Active orders', 'Awaiting pickup', 'On board', 'Failed', 'Returning']
            for d in driver_workloads().iterator(chunk_size=500):
                yield [d.user.get_full_name() or d.user.email or d.user.phone_number, d.user.phone_number, d.approval_status, d.availability_status, d.user.is_active, d.active_order_count, d.awaiting_pickup, d.on_board, d.failed, d.returning]
    writer = csv.writer(Echo())
    response = StreamingHttpResponse((writer.writerow([safe_cell(cell) for cell in row]) for row in rows()), content_type='text/csv; charset=utf-8')
    suffix = 'current' if kind in ['workloads', 'outstanding', 'failures', 'unrecorded'] else f'{start}-{end}'
    response['Content-Disposition'] = f'attachment; filename="oy-{kind}-{suffix}.csv"'
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required
def reports(request):
    if not request.user.is_staff:
        raise PermissionDenied()
    today = timezone.localdate()
    values = {'start': request.GET.get('start', (today-timedelta(days=29)).isoformat()), 'end': request.GET.get('end', today.isoformat())}
    form = ReportDates(values)
    if not form.is_valid():
        return render(request, 'frontend/reports.html', {'date_form': form}, status=400)
    start, end = form.cleaned_data['start'], form.cleaned_data['end']
    data = period_data(start, end)
    kind = request.GET.get('export')
    if kind:
        if kind not in ['deliveries', 'payments', 'workloads', 'outstanding', 'failures', 'unrecorded']:
            return render(request, 'frontend/reports.html', {'date_form': form, 'export_error': 'Choose a valid report export.'}, status=400)
        return export_csv(kind, data, start, end)
    unpaid = outstanding_payments()
    missing_payment = quoted_without_payment()
    data.update(date_form=form, start=start, end=end, delivered_rows=data['delivered'][:25], payment_rows=data['paid'][:25],
                unpaid_count=unpaid.count(), unpaid_amount=unpaid.aggregate(total=Sum('amount'))['total'] or Decimal('0.00'),
                unpaid_rows=unpaid.select_related('package_id__order_id').order_by('pk')[:25],
                missing_payment_rows=missing_payment.select_related('quote', 'order_id').order_by('pk')[:25], missing_payment_count=missing_payment.count(), missing_payment_amount=missing_payment.aggregate(total=Sum('quote__amount'))['total'] or Decimal('0.00'),
                failed_rows=unresolved_failures().select_related('package_id__order_id', 'rider__user').order_by('-assigned_at')[:25],
                failed_count=unresolved_failures().count(),
                drivers=driver_workloads(), missing_payment_date=Payment.objects.filter(payment_status='paid', paid_at__isnull=True).count(), missing_completion_date=Delivery.objects.filter(delivery_status='delivered', delivered_at__isnull=True).count())
    response = render(request, 'frontend/reports.html', data)
    response['Cache-Control'] = 'private, no-store'
    return response
