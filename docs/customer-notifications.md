# Customer delivery and payment updates

Customers have an **Updates** inbox with an unread count and a mark-as-read action. Each notification links to its order. Only its customer can list or mark it read.

Updates are created for:

- Whole-order pickup (one notification, regardless of package count).
- Individual package pickup, delivery completion and failed attempts.
- Administrator-authorized retries and returns, and handover back to the sender.
- Confirmed payment, after driver cash confirmation or administrator MoMo confirmation.
- Order cancellation.

Recording a MoMo transaction ID while payment remains pending does not generate a payment-confirmed message. Failed/returned packages do not trigger payment confirmation or refunds.

## Channels

Every update appears in-app. Email is queued only for a verified email; SMS is queued only for a verified phone. Customers with both verified receive both. Unverified optional contact details do not receive updates.

Emails use the existing SMTP setup. SMS uses the same Twilio sender/account configuration as OTP messages. If credentials/sender are missing, that channel remains pending without consuming provider retry attempts. In-app updates remain visible. No historical messages are invented during migration.

`PUBLIC_APP_URL` optionally supplies the public website base URL for order links in external messages. Without it, messages contain order/package identifiers and no website link. Set your actual HTTPS website URL for deployment.

## Queue and dispatch

Inbox items and outbound jobs are created in the transaction that records the delivery/payment event. They roll back together on failure. Provider requests occur after commit and outside row locks. A provider failure cannot reverse the operational update.

By default `NOTIFICATION_SEND_IMMEDIATELY=True` attempts external delivery after each event commits. Set it to false to queue outbound messages for a background worker. Network sends can add up to the configured provider timeouts to an immediate request; use queued mode for production responsiveness.

Run the existing application environment's command:

```sh
python manage.py send_notifications --limit 100
```

For automatic background processing and retries, configure the production scheduler to run this command every minute. This implementation supplies the command; it does not install a production scheduler. Failed jobs use backoff of 2, 4, 8, 16 and 32 minutes, with at most five provider attempts. Configuration-blocked jobs are checked again after 15 minutes without incrementing attempts.

To retry pending/failed jobs immediately after configuring a channel:

```sh
python manage.py send_notifications --retry-now --limit 100
```

Staff can inspect jobs in Django admin under Notification sends and use the retry-selected action. Attempt limits still apply. Provider errors are summarized without storing raw credential-bearing messages.

Workers claim jobs transactionally. A recently claimed job cannot be sent concurrently; stale claims may be recovered after 15 minutes. Successful jobs are not normally resent. As with an ordinary outbox, a crash after provider acceptance but before saving success can cause a duplicate on recovery; provider acceptance is not a handset/email delivery receipt. Queue rows marked sent mean the provider accepted the request, not that the recipient opened the message.

Before each attempt the current account/contact is rechecked. Changed or unverified destinations, and inactive accounts, cause the original job to be skipped rather than sent to an old contact.

## API

- `GET /api/v1/notifications/`: authenticated customer's own paginated inbox.
- `POST /api/v1/notifications/<id>/read/`: marks that customer's notification read; repeating it preserves the original read time.

The frontend inbox is `/notifications/`. Django session writes require CSRF as usual.

Apply migrations and restart after deployment. No additional provider package is needed for Twilio; the existing SMS adapter now supports both OTP and service updates.
