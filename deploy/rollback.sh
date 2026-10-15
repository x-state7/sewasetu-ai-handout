
#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ $# -ne 1 ]]; then
    echo "Usage: bash deploy/rollback.sh PREVIOUS_IMAGE_TAG"
    exit 1
fi

PREVIOUS_TAG="$1"

if [[ ! "$PREVIOUS_TAG" =~ ^[a-zA-Z0-9_.-]+$ ]]; then
    echo "Invalid image tag"
    exit 1
fi

if [[ ! -f .env ]]; then
    echo "Missing .env"
    exit 1
fi

echo "Requested application rollback to: $PREVIOUS_TAG"

echo
echo "This script does not restore or alter PostgreSQL."
echo "Before rollback, confirm the previous application image"
echo "is compatible with the current database schema."
echo

read -r -p "Enter ROLLBACK to proceed: " CONFIRM

if [[ "$CONFIRM" != "ROLLBACK" ]]; then
    echo "Rollback cancelled"
    exit 1
fi

# App images must be built and tagged before deployment.
export APP_IMAGE_TAG="$PREVIOUS_TAG"

docker compose -f docker-compose.yml \
    -f deploy/compose.rollback.yml \
    up -d --no-deps app

echo "Application container rollback requested."
echo "Verify logs and health before restoring public traffic."
