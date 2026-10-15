
#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/private-backups}"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DEST="$BACKUP_DIR/sevasetu-$STAMP.dump"
TEMP="$DEST.partial"

if [[ -e "$DEST" || -e "$TEMP" ]]; then
  echo "Backup filename already exists"
  exit 1
fi

trap 'rm -f "$TEMP"' ERR INT TERM

echo "Creating PostgreSQL backup..."

docker compose exec -T \
  -e PGPASSWORD \
  db sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-acl' \
  > "$TEMP"

if [[ ! -s "$TEMP" ]]; then
  echo "Backup failed: output is empty"
  exit 1
fi

mv "$TEMP" "$DEST"
trap - ERR INT TERM

echo "Backup created at:"
echo "$DEST"
echo "Verify restore capability in a separate database before migration."
