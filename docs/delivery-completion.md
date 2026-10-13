# Delivery completion and failed attempts

## Driver handover

A driver opens a picked-up package in the order page and enters **Received by**, the name of the person accepting the package. An optional JPEG/PNG delivery photo may be uploaded. The server records the handover timestamp, assigned driver and an immutable history event. A completion cannot be overwritten or repeated.

Photos are limited to 5 MB and 20 megapixels. They are decoded and reencoded as JPEG, scaled down to 2000 pixels and stripped of original metadata. The proof endpoint requires an authenticated order owner, assigned driver or staff account. Photo files are not served through a public media URL.

## Failed attempts and resolution

Drivers may record a failed attempt after pickup, selecting receiver unavailable, address not found, receiver refused, access issue or other. Other requires explanatory notes. The attempt counter increases and the reason/driver/time remain in the package history. Failed packages leave the active delivery route while waiting for a decision; the order stays in transit.

The administrator dashboard lists failed deliveries. Open their order and choose:

- **Retry**: authorize another delivery attempt with instructions. The package is still in the driver's custody and needs no second pickup. It reappears in route planning.
- **Return**: authorize return to the original pickup address with a reason. The route gains a return stop. The assigned driver confirms handover to the sender by entering the receiving person's name; the server records the return time.

A failed delivery cannot be completed directly; it needs a retry authorization. A returning package can only be marked returned. Customers cannot silently cancel failed/returning/returned packages; administrators use the resolution workflow.

Orders close as delivered when every package is delivered, returned when every package is returned, or completed with returns when the final outcomes are mixed. None of these states means cash/MoMo has been collected or refunded; payment confirmation remains a separate operation. Existing delivery records are preserved by migration, without invented historical proof or events.

## API changes

`PUT /api/v1/delivery/update/` accepts:

- `package_id` and `delivery_status` (`picked_up`, `delivered`, `failed`, `returned`).
- `received_by`: mandatory for delivered/returned.
- `proof_photo`: optional file, accepted only for delivered; use multipart form data for uploads.
- `failure_reason`: mandatory for failed; one of `receiver_unavailable`, `wrong_address`, `receiver_refused`, `access_issue`, `other`.
- `delivery_notes`: optional, up to 300 characters; required when failure reason is other.

Existing API clients must send `received_by` when completing delivery.

Staff-only `POST /api/v1/delivery/<id>/resolution/`: `action` (`retry` or `return`) and mandatory `reason` (up to 350 characters).

Authenticated owner/driver/staff endpoints:

- `GET /api/v1/delivery/<id>/history/` — timestamped events, actor IDs, attempt numbers and handover names.
- `GET /api/v1/delivery/<id>/proof/` — private JPEG photo, or 404 if unavailable.

Updates lock the order before the delivery and recheck permissions/status in the transaction. Competing completions/failures and retry/return decisions cannot create two outcomes. History and operational fields are read-only in Django admin; use the application actions.

## Deployment

Install updated requirements, apply migrations and restart the application. `DELIVERY_PROOF_ROOT` defaults to `private_media/` within the application directory. Set an absolute persistent private directory in production, writable by the application, and include it in backups. Do not expose it through the web server or static/media hosting. The directory is ignored by Git.

Route recalculation uses the configured Google API after failed-attempt resolution where automatic planning is enabled. A mapping failure does not undo a successful delivery decision. Drivers can update their starting address and recalculate remaining stops.
