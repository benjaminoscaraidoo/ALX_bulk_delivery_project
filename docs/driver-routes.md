# Driver delivery routes

A driver's dashboard combines all ready active orders into a single numbered route. It ends at the final delivery, without a return journey. Each order's pickup comes before its uncollected packages' delivery stops. Packages already picked up need no further pickup. Delivered and cancelled packages are removed when viewing the route.

Routes are prepared after deliveries are created or a ready order is assigned to a driver. An order is ready when its pickup address and every package's delivery record/address are present, with all deliveries assigned to the order's driver. Incomplete orders wait rather than being partially included. Creating several delivery records in one transaction only calculates one unchanged plan after commit.

The driver can use **Optimize my route** and enter their current starting address. For the first plan, the first pending pickup is used when no starting address is provided. This is a planned address, not live GPS tracking. When all packages are already collected and no previous origin is available, a starting address is required. Recalculate after moving or when deliveries change. Directions links open individual stops in Google Maps.

## Google configuration

The existing `GOOGLE_MAPS_API_KEY` is used server-side. Enable Google Routes API and billing, and allow Routes API in the key's restrictions. The system uses [Compute Route Matrix](https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRouteMatrix) for road driving times and distances. These requests incur Google charges per matrix element. No provider request is made just by opening the dashboard. Set `AUTO_ROUTE_PLANNING=False` to limit planning to the driver's button.

This first version supports up to **24 pickup and delivery stops** per driver plan (25 matrix locations including the starting point). Above that limit, the system asks for a smaller batch rather than omitting deliveries. Each order consumes one pickup stop while it has uncollected packages. Pickup and destination addresses are sent to Google to calculate routes.

The planner compares up to 64 promising mixed pickup/delivery paths at each step, alongside the original nearest-stop route, then improves the sequence by moving stops while preserving pickup precedence. It can deliver collected packages near or along the route to another pickup, without waiting for every order to be collected. Pickups at the starting point are completed before leaving that location. Driving time determines whether a mixed sequence is useful; area names alone do not determine the sequence. This is a heuristic, not a guarantee of the mathematical shortest route. Estimates exclude live traffic, time at stops, driver capacity and delivery time windows. It does not change delivery quotes, charges, assignment, payment or delivery status.

Provider failure keeps the previous stored plan and never cancels delivery creation. If addresses or assignments change, outdated stops are hidden until recalculation. Completed stops are removed without an extra provider charge; total estimates are hidden once the original plan has partly completed. If orders change during a mapping request, the result is rejected and the driver can retry.

## API

Authenticated drivers only; each request operates on the signed-in driver's own assignments:

- `GET /api/v1/driver/route/` — remaining ordered stops, planned origin, refresh flag and count of waiting orders.
- `POST /api/v1/driver/route/optimize/` — optional `starting_address` (up to 350 characters); returns a new plan or a clear validation/provider error.

The plan is persisted in `delivery.DriverRoutePlan`. Apply migrations before running the updated application.

## Recalculation triggers

A failed attempt removes that package from the route and forces a fresh calculation of remaining stops after commit. The driver can enter their current `starting_address` with the failed-attempt update; otherwise the saved route origin is used. This does not imply live GPS tracking. New ready assignments trigger planning for the receiving driver; reassignment also forces recalculation for the previous driver. Incomplete orders wait until their delivery records are ready. Completed stops are pruned without a paid recalculation.
