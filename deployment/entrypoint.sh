#!/bin/sh
set -eu
python - <<'PY'
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bulk_delivery_project.settings')
from django.conf import settings
if settings.PRODUCTION:
    if settings.DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
        raise SystemExit('Configure DATABASE_URL for PostgreSQL before starting the production container.')
    if not settings.REDIS_URL:
        raise SystemExit('Configure REDIS_URL for shared production request limits before starting the container.')
PY
exec "$@"
