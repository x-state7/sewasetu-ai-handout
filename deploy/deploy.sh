
#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "Seva Setu deployment preflight"

if [[ ! -f .env ]]; then
    echo "Missing private .env file"
    exit 1
fi

set -a
source .env
set +a

python3 deploy/preflight.py

echo "Validating Docker Compose configuration..."
docker compose config --quiet

echo "Static checks completed."
echo
echo "Required before production cutover:"
echo "1. Verify a successful PostgreSQL backup and restore rehearsal"
echo "2. Apply migrations 001 and 002 in sequence"
echo "3. Confirm Step 4 MCP SDK compatibility"
echo "4. Confirm OAuth JWKS and resource discovery"
echo "5. Start private services and inspect logs"
echo "6. Execute Step 5 evaluations"
echo "7. Verify TLS, authorization and full application workflows"
echo
echo "No migrations or production cutover were executed."
