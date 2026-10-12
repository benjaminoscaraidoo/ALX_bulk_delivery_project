# Deploying Parcel on PythonAnywhere

Use the reviewed branch containing all fixes, or merge it into main before deploying. This guide changes server configuration; local settings and tariff edits do not automatically update the server.

## Before updating

Back up the server database and private configuration. Stop accepting writes while backing up and migrating. Verify that the web app and its virtual environment use Python 3.12 or newer for Django 6. Install the project's requirements in that environment.

Existing negative payment amounts or duplicate nonempty transaction references on paid payments must be corrected before applying the payment-constraint migration. Do not delete historical payments to make migration succeed; reconcile the records first.

## Private server configuration

Put these values in the server checkout's private `.env` (beside manage.py), or set them in the web process environment. Use your own newly generated secret and credentials, never the sample placeholders:

```dotenv
DJANGO_ENV=production
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=benjaminoscaraidoo.pythonanywhere.com
DJANGO_SECRET_KEY='new-private-random-secret'
EMAIL_ADDRESS='your-email-address'
EMAIL_HOST_PASSWORD='your-email-app-password'
GOOGLE_MAPS_API_KEY='your-private-routes-key'
DJANGO_TRUST_PROXY=False
DJANGO_HSTS_SECONDS=3600
DJANGO_HSTS_INCLUDE_SUBDOMAINS=False
```

Ensure Routes API and billing are enabled for the Google key. Changing the Django secret invalidates old signed tokens and sessions. Do not publish `.env`.

PythonAnywhere terminates HTTPS before forwarding requests to the Django app. Confirm that your hosting setup supplies a trusted `X-Forwarded-Proto` header, stripping client-supplied values, then set `DJANGO_TRUST_PROXY=True`. Do this before enabling production mode on the live web process; otherwise HTTPS redirects can loop. Turn on PythonAnywhere's **Force HTTPS** setting as well, so static files are covered.

Production cookies require HTTPS. Local preview uses `DJANGO_ENV=local`, no HTTPS redirect, and no secure-cookie requirement. Do not use local mode on the public deployment.

The initial one-hour HSTS period is intentionally short. Increase it only after checking HTTPS on every intended hostname. Enable subdomain HSTS only if all subdomains use HTTPS. Preload remains off; no browser preload submission is performed by this project. The deployment check reports advisories for these two deliberate choices.

## Update, migrate, and collect static files

From the server checkout with its matching virtual environment active:

```bash
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py spectacular --validate --fail-on-warn --file /tmp/parcel-schema.yaml
python manage.py check --deploy
```

Set PythonAnywhere's virtualenv path on the Web tab. In the host's WSGI configuration, add the actual server checkout to `sys.path` and set `DJANGO_SETTINGS_MODULE` to `bulk_delivery_project.settings` before calling `get_wsgi_application()`. The project's settings load `.env` from the checkout, independent of the shell working directory.

In **Web → Static files**, map `/static/` to the actual server checkout's `staticfiles` directory (`STATIC_ROOT`). Do not point it at the frontend source folder; collectstatic also gathers admin and API assets. Reload the web app after code, configuration, migrations and static-file collection are complete. Never deploy using runserver or its --insecure option.

## Prices and administrator access

Create the first administrator in a server console:

```bash
python manage.py createsuperuser
```

Existing administrators remain valid. In Django admin, set delivery-area prices to Kumasi GHS 60, Takoradi GHS 25, and Tamale GHS 25. The initial distance brackets are seeded by migrations (10 km / 35, 25 km / 50, 30 km / 60); administrators can edit them. New destinations default to no configured price until staff sets one. Quoted prices remain unchanged when tariffs change.

## Verify before reopening writes

Check login, CSS and JavaScript, customer registration email, Google driving-distance quote, an outside-Accra quote, order pickup/delivery, driver cash confirmation, MoMo ID capture, and administrator MoMo confirmation. Verify that HTTP redirects to HTTPS and customer/driver pages reject unrelated accounts. Do not record real payments during a smoke test unless actually received.

## Rollback

Retain the previous checkout and database backup. If deployment fails, restore the matching code and database together while writes are stopped. Avoid blindly reversing financial migrations or restoring a stale database after accepting new orders. Review data written since the backup before reopening service.

References:
- https://help.pythonanywhere.com/pages/DjangoStaticFiles
- https://blog.pythonanywhere.com/167/
- https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/
