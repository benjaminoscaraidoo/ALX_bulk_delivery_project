"""Open driving routes with pickup precedence; never modifies delivery prices."""
import json
import math
import logging
from urllib.request import Request, urlopen
from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import APIException, ValidationError
from customer.models import DriverProfile
from order.models import Order
from .models import Delivery, DriverRoutePlan

logger = logging.getLogger(__name__)
MAX_STOPS = 24


class RoutingUnavailable(APIException):
    status_code = 503
    default_detail = 'Driving routes are unavailable. Please try again later.'


def collect_stops(driver_id):
    stops, waiting = [], 0
    orders = Order.objects.filter(driver_id_id=driver_id, order_status__in=['pending', 'assigned', 'in_transit']).prefetch_related('packages__deliveries').order_by('created_at', 'pk')
    for order in orders:
        packages = list(order.packages.all())
        deliveries = [(p, getattr(p, 'deliveries', None)) for p in packages]
        if not packages or not order.pickup_address or any(d is None or d.rider_id != driver_id or not (d.address or p.delivery_address).strip() for p, d in deliveries):
            waiting += 1
            continue
        remaining = [(p, d) for p, d in deliveries if d.delivery_status in ['assigned', 'picked_up']]
        pickup_key = f'pickup:{order.pk}'
        if any(d.delivery_status == 'assigned' for p, d in remaining):
            stops.append(dict(key=pickup_key, kind='pickup', address=order.pickup_address.strip(), order_id=order.pk, requires=None))
        for package, delivery in remaining:
            stops.append(dict(key=f'delivery:{delivery.pk}', kind='delivery', address=(delivery.address or package.delivery_address).strip(), order_id=order.pk, package_id=package.pk, delivery_id=delivery.pk, recipient=package.receiver_name, requires=pickup_key if delivery.delivery_status == 'assigned' else None))
    return stops, waiting


def driving_matrix(addresses):
    if not settings.GOOGLE_MAPS_API_KEY:
        raise RoutingUnavailable('Configure the Google Maps API key to plan driving routes.')
    waypoints = [{'waypoint': {'address': address}} for address in addresses]
    request = Request('https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix', data=json.dumps({'origins': waypoints, 'destinations': waypoints, 'travelMode': 'DRIVE', 'routingPreference': 'TRAFFIC_UNAWARE'}).encode(), headers={'Content-Type': 'application/json', 'X-Goog-Api-Key': settings.GOOGLE_MAPS_API_KEY, 'X-Goog-FieldMask': 'originIndex,destinationIndex,status,condition,distanceMeters,duration'}, method='POST')
    n = len(addresses)
    matrix = [[None] * n for _ in addresses]
    try:
        with urlopen(request, timeout=20) as response:
            entries = json.loads(response.read(2_000_000))
        for entry in entries:
            i, j = entry.get('originIndex', 0), entry.get('destinationIndex', 0)
            if type(i) is not int or type(j) is not int or not (0 <= i < n and 0 <= j < n):
                raise ValueError()
            if entry.get('status', {}).get('code', 0) or entry.get('condition') != 'ROUTE_EXISTS':
                raise ValueError()
            duration = entry.get('duration', '0s')
            if not isinstance(duration, str) or not duration.endswith('s'):
                raise ValueError()
            seconds = float(duration[:-1])
            meters = entry.get('distanceMeters', 0)
            if not math.isfinite(seconds) or seconds < 0 or type(meters) is not int or meters < 0:
                raise ValueError()
            if matrix[i][j] is not None:
                raise ValueError()
            matrix[i][j] = (seconds, meters)
        if any(value is None for row in matrix for value in row):
            raise ValueError()
    except Exception as error:
        raise RoutingUnavailable() from error
    return matrix


def sequence_stops(stops, matrix):
    """Nearest feasible stop followed by precedence-safe relocation improvements."""
    remaining, visited, route, current = list(range(len(stops))), set(), [], 0
    while remaining:
        candidates = [i for i in remaining if not stops[i]['requires'] or stops[i]['requires'] in visited]
        if not candidates:
            raise ValidationError('The pickup sequence is invalid.')
        chosen = min(candidates, key=lambda i: (matrix[current][i + 1][0], i))
        route.append(chosen)
        visited.add(stops[chosen]['key'])
        remaining.remove(chosen)
        current = chosen + 1

    def cost(indices):
        nodes = [0] + [i + 1 for i in indices]
        return sum(matrix[a][b][0] for a, b in zip(nodes, nodes[1:]))

    def feasible(indices):
        seen = set()
        for i in indices:
            if stops[i]['requires'] and stops[i]['requires'] not in seen:
                return False
            seen.add(stops[i]['key'])
        return True

    # Strict improvement terminates; bounded passes keep response time predictable.
    for _ in range(len(stops)):
        best, best_cost = route, cost(route)
        for old in range(len(route)):
            shortened = route[:old] + route[old + 1:]
            for new in range(len(route)):
                candidate = shortened[:new] + [route[old]] + shortened[new:]
                candidate_cost = cost(candidate)
                if candidate_cost < best_cost and feasible(candidate):
                    best, best_cost = candidate, candidate_cost
        if best == route:
            break
        route = best
    nodes = [0] + [i + 1 for i in route]
    legs = [matrix[a][b] for a, b in zip(nodes, nodes[1:])]
    return [stops[i] for i in route], math.ceil(sum(s for s, m in legs)), sum(m for s, m in legs)


def current_route(driver_id):
    fresh, waiting = collect_stops(driver_id)
    plan = DriverRoutePlan.objects.filter(driver_id=driver_id).first()
    result = dict(stops=[], waiting_orders=waiting, needs_refresh=bool(fresh), starting_address='', generated_at=None, distance_meters=None, duration_seconds=None)
    if not plan:
        return result
    result.update(starting_address=plan.starting_address, generated_at=plan.generated_at)
    old = {stop['key']: stop for stop in plan.stops}
    # Completed pickups no longer appear as prerequisites, so compare identity/address.
    def same(a, b):
        return {k: v for k, v in a.items() if k != 'requires'} == {k: v for k, v in b.items() if k != 'requires'}
    if any(stop['key'] not in old or not same(stop, old[stop['key']]) for stop in fresh):
        return result
    fresh_by_key = {stop['key']: stop for stop in fresh}
    result['stops'] = [fresh_by_key[stop['key']] for stop in plan.stops if stop['key'] in fresh_by_key]
    result['needs_refresh'] = False
    if len(fresh) == len(plan.stops):
        result.update(distance_meters=plan.distance_meters, duration_seconds=plan.duration_seconds)
    return result


def optimize_route(driver_id, starting_address='', force=True):
    stops, waiting = collect_stops(driver_id)
    if not stops:
        raise ValidationError('No ready deliveries to arrange. Add delivery locations and assign a driver first.')
    if len(stops) > MAX_STOPS:
        raise ValidationError('This route has more than 24 pickup and delivery stops. Plan smaller batches before optimizing.')
    current = current_route(driver_id)
    if not force and not current['needs_refresh']:
        return current
    origin = starting_address.strip() or current['starting_address'] or next((stop['address'] for stop in stops if stop['kind'] == 'pickup'), '')
    if not origin:
        raise ValidationError('Enter your current starting address to arrange packages already picked up.')
    matrix = driving_matrix([origin] + [stop['address'] for stop in stops])
    ordered, seconds, meters = sequence_stops(stops, matrix)
    with transaction.atomic():
        # Same order-before-driver locking order as assignment and delivery updates.
        list(Order.objects.select_for_update().filter(driver_id_id=driver_id).order_by('pk'))
        DriverProfile.objects.select_for_update().get(pk=driver_id)
        fresh, _ = collect_stops(driver_id)
        if fresh != stops:
            raise ValidationError('Deliveries changed while planning. Please optimize again.')
        DriverRoutePlan.objects.update_or_create(driver_id=driver_id, defaults=dict(starting_address=origin, stops=ordered, distance_meters=meters, duration_seconds=seconds))
    return current_route(driver_id)


def auto_optimize(driver_id):
    if not settings.AUTO_ROUTE_PLANNING:
        return
    try:
        optimize_route(driver_id, force=False)
    except APIException:
        # A failed mapping request must not fail an otherwise valid delivery creation.
        logger.warning('Driver route needs manual refresh for driver %s.', driver_id)


def schedule_route(driver_id):
    if driver_id:
        transaction.on_commit(lambda: auto_optimize(driver_id))
