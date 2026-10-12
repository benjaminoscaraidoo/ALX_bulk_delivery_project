import json
from decimal import Decimal
from urllib.request import Request, urlopen
from urllib.error import URLError

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from rest_framework.exceptions import APIException, ValidationError
from .models import Package, Order, DistanceTariff, DeliveryQuote


class RoutingUnavailable(APIException):
    status_code = 503
    default_detail = 'Driving distance is unavailable. Please try again later.'


def driving_distance(origin, destination):
    if not settings.GOOGLE_MAPS_API_KEY:
        raise RoutingUnavailable('Google Routes is not configured.')
    request = Request('https://routes.googleapis.com/directions/v2:computeRoutes',
        data=json.dumps({'origin': {'address': origin}, 'destination': {'address': destination},
                         'travelMode': 'DRIVE', 'routingPreference': 'TRAFFIC_UNAWARE',
                         'computeAlternativeRoutes': False}).encode(),
        headers={'Content-Type': 'application/json', 'X-Goog-Api-Key': settings.GOOGLE_MAPS_API_KEY,
                 'X-Goog-FieldMask': 'routes.distanceMeters'}, method='POST')
    try:
        with urlopen(request, timeout=10) as response:
            distance = json.load(response)['routes'][0]['distanceMeters']
        if isinstance(distance, bool) or not isinstance(distance, int) or distance < 0:
            raise ValueError('Invalid distance')
        return distance
    except (URLError, TimeoutError, OSError, ValueError, KeyError, IndexError, TypeError):
        raise RoutingUnavailable()


def create_quote(package_id, user, manual_amount=None, reason=''):
    package = Package.objects.select_related('order_id', 'delivery_area').get(pk=package_id)
    if package.order_id.customer_id_id != user.pk and not user.is_staff:
        raise ValidationError('You can only quote your own packages.')
    if manual_amount is not None and not user.is_staff:
        raise ValidationError('Only administrators can set manual quotes.')
    if DeliveryQuote.objects.filter(package=package).exists():
        if manual_amount is not None:
            raise ValidationError('Existing quotes cannot be changed.')
        return package.quote, None
    origin, destination = package.order_id.pickup_address, package.delivery_address
    if not origin or not destination:
        raise ValidationError('Pickup and package delivery addresses are required.')
    distance = None if package.outside_accra else driving_distance(origin, destination)
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=package.order_id_id)
        package = Package.objects.select_for_update().select_related('delivery_area').get(pk=package.pk)
        if DeliveryQuote.objects.filter(package=package).exists():
            return package.quote, None
        if order.order_status not in [Order.Status.PENDING, Order.Status.ASSIGNED]:
            raise ValidationError('Quotes can only be created before pickup.')
        if origin != order.pickup_address or destination != package.delivery_address:
            raise ValidationError('Addresses changed. Please request a new quote.')
        if package.outside_accra:
            area = package.delivery_area
            if not area or not area.enabled:
                raise ValidationError('Select an enabled delivery area.')
            amount = area.charge
            quote_reason = f'Outside Accra: {area.name}'
        else:
            tariff = DistanceTariff.objects.filter(enabled=True, upper_km__gte=Decimal(distance) / 1000).order_by('upper_km').first()
            amount = tariff.charge if tariff else None
            quote_reason = f'Up to {tariff.upper_km} km' if tariff else 'Administrator quote required'
        if manual_amount is not None:
            if amount is not None:
                raise ValidationError('This route already has a configured tariff.')
            if not reason.strip():
                raise ValidationError('A reason is required for a manual quote.')
            amount, quote_reason = manual_amount, reason
        if amount is None:
            return None, distance
        quote = DeliveryQuote.objects.create(package=package, amount=amount, distance_meters=distance,
            pickup_address=origin, delivery_address=destination, outside_accra=package.outside_accra,
            area_name=package.delivery_area.name if package.delivery_area else '', reason=quote_reason)
        order.total_price = DeliveryQuote.objects.filter(package__order_id=order).aggregate(total=Sum('amount'))['total'] or 0
        order.save(update_fields=['total_price'])
        return quote, None
