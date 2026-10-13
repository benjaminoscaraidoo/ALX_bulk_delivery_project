#!/bin/sh
set -eu
umask 077
# Run from the checkout containing compose.yaml. This creates a backup, never a restore.
backup_dir=${1:-backups}
mkdir -p "$backup_dir"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
docker compose exec -T db pg_dump -U oy_delivery -d oy_delivery -Fc > "$backup_dir/database-$stamp.dump"
docker compose run --rm --no-deps --user root web tar -czf - -C /app/private_media . > "$backup_dir/delivery-photos-$stamp.tar.gz"
printf 'Saved database and delivery photo backups in %s\n' "$backup_dir"
