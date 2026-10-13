# Portable OY Delivery Services deployment

The project can run on a Linux server or a host supporting Python/Docker, PostgreSQL, Redis and a separate worker. No hosting account is provisioned and no existing database is changed by these files.

## Runtime

- Python 3.12+; install `requirements.txt`.
- PostgreSQL connection in `DATABASE_URL`; omission retains SQLite for local development.
- Redis in `REDIS_URL` to share request/login/OTP limits across workers.
- Gunicorn web process: `gunicorn bulk_delivery_project.wsgi:application --config gunicorn.conf.py`.
- Notification process: `python manage.py send_notifications --watch --interval 60`.
- Persistent private photo directory in `DELIVERY_PROOF_ROOT`.
- WhiteNoise serves collected static files. It does not expose private delivery photos.

The Docker image defaults to production. Its entrypoint requires PostgreSQL and Redis configuration rather than starting with an ephemeral SQLite database. `PORT` and `WEB_CONCURRENCY` are configurable. The container runs as a non-root application user.

## Private configuration

Set values on the host or in its private `.env`. Keep the existing secret if preserving sessions/tokens; no key rotation is performed by this setup.

```dotenv
DJANGO_ENV=production
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=your-existing-private-secret
DJANGO_ALLOWED_HOSTS=delivery.example.com,localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=https://delivery.example.com
DATABASE_URL=postgresql://oy_delivery:URL_ENCODED_PASSWORD@db:5432/oy_delivery
POSTGRES_PASSWORD=your-private-database-password
REDIS_URL=redis://redis:6379/0
PUBLIC_APP_URL=https://delivery.example.com
NOTIFICATION_SEND_IMMEDIATELY=False
EMAIL_ADDRESS=your-email-address
EMAIL_HOST_PASSWORD=your-email-app-password
GOOGLE_MAPS_API_KEY=your-private-routes-key
```

For managed PostgreSQL/Redis use the provider's connection URL and TLS configuration instead of the Compose hostnames. URL-encode the database password in `DATABASE_URL`; `POSTGRES_PASSWORD` contains its original value. Keep the same password/account/database in both variables for Compose.

Twilio values are the existing account, token and sender/Messaging Service settings. SMS jobs remain pending until the sender is configured. SMTP, Google and Twilio credentials never enter the Docker build. `.dockerignore` excludes private environment files, database files, photos and backups.

## HTTPS

Use the host's HTTPS load balancer or a reverse proxy with your domain/certificate. Compose binds web port 8000 only to localhost; database and Redis have no published host ports. Configure the proxy to preserve Host and strip client-supplied forwarded-protocol headers before setting its own `X-Forwarded-Proto`.

After confirming this trusted proxy setup, set `DJANGO_TRUST_PROXY=True`. Production redirects plain HTTP to HTTPS and uses secure session/CSRF cookies. Configure health checks through HTTPS, or with trusted HTTPS forwarding, at `/health/`. The endpoint returns 200 when the application can query its database and 503 without connection details when it cannot. It does not certify email/SMS availability.

Subdomain HSTS and preload remain intentionally off until all intended domains are confirmed. `check --deploy` therefore reports the two documented HSTS advisories.

## Compose on a server

From the checkout with the server's private `.env` configured:

```sh
docker compose build
docker compose up -d db redis
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
docker compose run --rm web python manage.py check --deploy
docker compose up -d web worker
```

The image collects static assets during build using build-only placeholders, not production credentials. Database migrations are an explicit release step, not run independently by every web worker. New databases get the seeded tariffs; configure outside-Accra area prices through admin.

For an existing database, preserve administrator accounts and do not create replacements unnecessarily. If moving SQLite data to PostgreSQL, first rehearse a reviewed data transfer on staging, preserving numeric identifiers, users, quotes, payments, history, notification state and photo filenames. Review user/group permissions during the transfer. Do not point a live service at an empty replacement database and assume the old records moved automatically. Fixture restore hooks now ignore raw restored rows, so they do not reassign drivers or regenerate customer messages.

The web container's `delivery_photos` volume is persistent. PostgreSQL uses `postgres_data`. Keep these volumes when replacing app containers. The worker continuously retries due jobs; no separate cron job is required in this setup. Watch its logs and use Notification sends in admin to investigate failures.

## Backups and restore rehearsal

For Compose, the supplied script creates a PostgreSQL custom-format dump and a photo archive in a private directory:

```sh
./deployment/backup-compose.sh backups
```

Copy each matching database/photo pair to encrypted off-server storage. Schedule the script through the server's backup scheduler and verify retention and restore periodically. Backup scheduling/off-server storage is not installed by the repository.

To rehearse a restore, use an isolated staging database and photo volume, with workers stopped and outbound notification sending disabled. Restore the database using `pg_restore`, restore its matching photo archive, verify photo ownership for UID 10001, then check order/payment counts, tariffs, driver assignments, audit events and recipient photo access. Pending job state must be reviewed before restarting outbound workers.

For a production restore, pause writes and workers, back up the current state, restore the matching code/schema/database/photos, reconcile anything written after the backup, and reopen only after validation. Do not blindly restore an old payment ledger over newer transactions.

## Current validation limits

The isolated operational trial exercises three orders/14 packages, pickup constraints, retry/return, 13 successful deliveries, one return, cash/MoMo confirmation, 34 customer updates and administrator reports. Provider responses are mocked and no real payments/messages are generated. A prior Google scenario tested live driving estimates separately.

Gunicorn startup, database health response, static serving, deployment checks, Compose configuration and shell syntax are verified locally. Docker is not runnable on the current machine (its Desktop executable is missing), so image build, PostgreSQL execution, container volumes and actual backup restore need validation on a Docker-capable staging host. Production email delivery, Twilio sender delivery and HTTPS/domain checks require the chosen host and real configuration.

References: [Django databases](https://docs.djangoproject.com/en/6.0/ref/databases/), [Django fixture signals](https://docs.djangoproject.com/en/6.0/ref/signals/), [Gunicorn](https://gunicorn.org/).
