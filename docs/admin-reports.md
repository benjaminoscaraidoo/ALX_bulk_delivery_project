# Administrator reports

Staff accounts can open **Reports** in the navigation, at `/reports/`. Customers, drivers and unauthenticated visitors cannot download these reports.

The activity date range defaults to the last 30 days, including today. Dates are inclusive:

- Orders created: order creation date.
- Packages delivered: recorded delivery completion timestamp.
- Confirmed payments: paid/confirmation date, split by cash and mobile money.
- Failed attempts: timestamped failed-attempt history events. Several failures for one package count as several attempts, even if the package later succeeds.
- Packages returned: recorded sender-return timestamp. Returns are not counted as successful deliveries.

Period receipts include only payments marked paid and exclude quotes and pending payments. A confirmed payment remains a historical receipt even if its order is later cancelled; the system has no automatic refunds. Historical records missing completion or confirmation dates are excluded from period totals and flagged on the page.

The **current backlog** covers all dates, regardless of the selected activity range:

- Recorded pending/failed payments, excluding cancelled orders. Returning/returned packages do not automatically clear payment balances.
- Quoted packages without a recorded payment method. Unquoted packages have no known amount and are excluded from this financial total.
- Failed deliveries awaiting administrator resolution.
- Each driver's active orders, packages awaiting pickup, packages on board, failed packages and packages returning to sender. Counts exclude closed/cancelled orders and do not multiply when a driver has several orders and packages. Inactive driver accounts remain visible so parcels in their custody can be followed up.

Delivery and payment tables show up to 25 records. CSV downloads include every matching record for completed deliveries, confirmations, outstanding payments, unrecorded payment methods, failed deliveries and driver workloads. Workload/backlog exports are labelled current and ignore the activity period, as their on-screen sections explain. Spreadsheet formula-leading text is escaped in exports.

All report access and exports require a staff account. The views are read-only and do not confirm payments, assign drivers, change delivery states or send customer updates. Dates/times use the application's configured timezone (currently UTC, matching Accra).
