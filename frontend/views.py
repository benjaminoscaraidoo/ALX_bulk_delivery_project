import math
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from order.models import Order, DeliveryArea
from delivery.models import Payment, Delivery
from delivery.routing import current_route
from customer.models import DriverProfile
from customer.throttles import LoginThrottle


class EmailLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Phone number or email'
        self.fields['username'].widget.attrs.update({'type': 'text', 'autocomplete': 'username', 'placeholder': '+233… or you@example.com'})
        self.fields['password'].widget.attrs.update({'placeholder': 'Your password'})


class SignInView(LoginView):
    template_name = 'frontend/login.html'
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        throttle = LoginThrottle()
        if not throttle.allow_request(request, self):
            response = render(request, self.template_name, {
                'form': self.authentication_form(request),
                'throttle_error': 'Too many sign-in attempts. Please wait a minute and try again.',
                'next': request.POST.get('next', ''),
            }, status=429)
            response['Retry-After'] = str(max(1, math.ceil(throttle.wait() or 60)))
            return response
        return super().post(request, *args, **kwargs)


def orders_for(user):
    queryset = Order.objects.select_related('driver_id__user').prefetch_related('packages__quote', 'packages__deliveries', 'packages__payment')
    if user.is_staff:
        return queryset
    if user.role == 'driver':
        return queryset.filter(driver_id__user=user)
    return queryset.filter(customer_id=user)


@login_required
def dashboard(request):
    orders = orders_for(request.user).order_by('-created_at', '-id')
    active = orders.exclude(order_status__in=['cancelled', 'delivered', 'returned', 'completed_returns'])
    payments = Payment.objects.filter(payment_status='pending', payment_method='mobile_money').select_related('package_id__order_id') if request.user.is_staff else Payment.objects.none()
    route = current_route(request.user.driverprofile.pk) if request.user.role == 'driver' else None
    if route and route['distance_meters'] is not None:
        route['distance_km'] = route['distance_meters'] / 1000
        route['driving_minutes'] = math.ceil(route['duration_seconds'] / 60)
    return render(request, 'frontend/dashboard.html', {
        'orders': orders[:40], 'active_count': active.count(),
        'driver_route': route,
        'failed_deliveries': Delivery.objects.filter(delivery_status='failed').select_related('package_id__order_id').order_by('-assigned_at')[:40] if request.user.is_staff else [],
        'completed_count': orders.filter(order_status='delivered').count(),
        'order_count': orders.count(), 'payments': payments[:40],
        'drivers': DriverProfile.objects.select_related('user').filter(approval_status='pending')[:40] if request.user.is_staff else [],
    })


@login_required
def order_detail(request, pk):
    order = get_object_or_404(orders_for(request.user), pk=pk)
    return render(request, 'frontend/order.html', {
        'order': order, 'packages': order.packages.select_related('delivery_area', 'deliveries').prefetch_related('deliveries__events').all(),
        'areas': DeliveryArea.objects.filter(enabled=True).order_by('name'),
        'editable': order.order_status in ['pending', 'assigned'],
        'can_cancel': order.order_status not in ['cancelled', 'delivered', 'returned', 'completed_returns'] and not Delivery.objects.filter(package_id__order_id=order, delivery_status__in=['delivered', 'failed', 'returning', 'returned']).exists(),
        'pricing_complete': order.packages.exists() and not order.packages.filter(quote__isnull=True).exists(),
    })


@login_required
def profile(request):
    if request.user.role == 'customer':
        profile = request.user.customer_profile
    elif request.user.role == 'driver':
        profile = request.user.driverprofile
    else:
        return render(request, 'frontend/profile.html', {'staff_profile': True})
    return render(request, 'frontend/profile.html', {'profile': profile})


def account(request, kind):
    if kind not in ['register', 'password-reset']:
        raise PermissionDenied()
    return render(request, 'frontend/account.html', {'kind': kind})


@login_required
def notifications(request):
    from django.core.paginator import Paginator
    from notifications.models import Notification
    items = Notification.objects.filter(customer=request.user).select_related('order')
    return render(request, 'frontend/notifications.html', {'page_obj': Paginator(items, 20).get_page(request.GET.get('page'))})
