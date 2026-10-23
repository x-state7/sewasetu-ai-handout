# Deploy the complete SevaSetu Step 6/7 codebase on AWS EC2

This deployment copy was built from `sewasetu-ai-handout(1).zip` supplied in the current conversation.
It retains the complete Flask, OAuth, MCP citizen/officer, and evaluation code.
The historical `.git`, `.env`, `.pyc`, and Director audio are excluded to avoid bundling credentials and noise.
**Keep the original ZIP/repository to preserve your internship Git history.**

## Changes made specifically for an AWS / public demo

1. Removed the stray `);` from `app/schema.sql` (fresh DB initialization failure).
2. Updated Flask, Requests and Gunicorn compatibility/security baselines; Docker still uses Python 3.11.
3. Changed the web Gunicorn workers from four to two for a t3.small (2 GiB RAM).
4. Installed `ca-certificates` in the application image; pinned HTTPX2 to the supported major line.
5. Added service restart policies; all database/MCP/evaluation ports remain internal. Only Caddy uses public ports 80/443.
6. Made optional evaluation bearer tokens optional at Compose parse time. The evaluation runner still requires real tokens when invoked.
7. Corrected the database backup script's `PGPASSWORD` invocation.
8. Restored DB-backed, revocation-aware checks for authorized officer program tokens.
9. Made fresh public installations use synthetic `seed/demo-seed.sql`, while **retaining** the original production-labeled `seed/seed.sql` solely as an opt-in reference.
10. Added a private environment generator and expanded configuration preflight checks.

## Before deploying

- EC2 Ubuntu 26.04 or 24.04 amd64, t3.small, 20 GiB gp3, and a working `ubuntu` SSH login.
- EC2 security group: SSH `22` from **your IP only**; TCP `80` and `443` from the internet; no public `5432`, `8000`, `8011`, `8012`, `8025`.
- Register a free hostname such as `YOURNAME.duckdns.org` and point its A record to the instance's public IPv4 address (the address may change after a stop/start).
- Do not use a public Git repository for `.env` or private documents.
- Free AWS credits are limited; monitor EC2/EBS/public IPv4 consumption in Billing.

## A. Install Docker + Compose inside the EC2 SSH shell

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y unzip ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker compose version
```

Use `sudo docker ...` instead of adding the `ubuntu` account to the root-equivalent Docker group.

## B. Upload this ZIP from your **local laptop**, then extract on EC2

```bash
# Run on your laptop; substitute the current public EC2 IP.
scp -i ~/.ssh/sevasetu-key.pem "$HOME/Downloads/sewasetu-aws-complete-latest.zip" ubuntu@YOUR_PUBLIC_IP:~/
ssh -i ~/.ssh/sevasetu-key.pem ubuntu@YOUR_PUBLIC_IP

# The following run inside EC2:
mkdir -p ~/sevasetu
unzip -q ~/sewasetu-aws-complete-latest.zip -d ~/sevasetu
cd ~/sevasetu/sewasetu-ai-handout
```

## C. Make HTTPS hostname and secrets

1. Update DNS A record to point at EC2. Check with `getent ahostsv4 YOURNAME.duckdns.org`.
2. Create fresh production secrets, not the old uploaded `.env`:

```bash
python3 deploy/generate_aws_env.py YOURNAME.duckdns.org
set -a
. ./.env
set +a
python3 deploy/preflight.py
sudo docker compose config --quiet
```

Keep `.env` mode `600` and never post its contents in chat. The generator does not print secrets.

## D. Bring up the services (fresh database)

This project already includes **Caddy**, so do not install a second proxy on ports 80/443.
If you previously installed Nginx, stop it first:

```bash
sudo systemctl disable --now nginx 2>/dev/null || true
cd ~/sevasetu/sewasetu-ai-handout
# Avoid parallel builds on a 2 GiB EC2 VM:
sudo env COMPOSE_PARALLEL_LIMIT=1 docker compose build app smsgw
sudo docker compose up -d db smsgw
sudo docker compose logs --tail=60 db
sudo docker compose exec -T db psql -U sewasetu -d sewasetu -c 'select count(*) from applications;'
# SYNTHETIC DEMO SEED EXPECTATION: 12 rows.
sudo docker compose up -d app mcp-citizen mcp-officer scheduler eval-public proxy
sudo docker compose ps
sudo docker compose logs --tail=80 proxy app mcp-citizen mcp-officer
```

First boot creates tables from `app/schema.sql` and demo records from `seed/demo-seed.sql`.
**Important:** these init scripts only run on a brand-new Postgres volume, and should **never** be applied wholesale to an existing DB. For an existing DB, back up first and apply only missing migrations 001/002/003 in order. Do not use `docker compose down -v` on real data.

## E. Browser and API smoke checks

```bash
# Run on EC2 after DNS resolves and TLS is issued.
DOMAIN=YOURNAME.duckdns.org
curl -i "https://$DOMAIN/" -o /dev/null -w 'HTTP %{http_code}\n'
curl -sS -o /dev/null -w 'oauth HTTP %{http_code}\n' "https://$DOMAIN/.well-known/oauth-authorization-server"
curl -sS -o /dev/null -w 'jwks HTTP %{http_code}\n' "https://$DOMAIN/.well-known/jwks.json"
curl -sS -o /dev/null -w 'evaluation HTTP %{http_code}\n' "https://$DOMAIN/eval-dashboard"
```

Visit `https://YOURNAME.duckdns.org/`. Check administrator login, portal OTP flow (simulated SMS inbox is available only after admin login), application submission, file upload, status tracking, and authenticated MCP/OAuth actions. The public evaluation page correctly starts empty until a genuine test run. MCP may correctly respond `401` to unauthenticated requests.

**New: Full agent + SQL evaluation:** Follow [`app/evaluation/README.md`](app/evaluation/README.md)
for fresh synthetic personas, three real OAuth test identities, a working tool-calling
LLM, and a one-time document ticket. The `eval-agent` profile service produces
PostgreSQL-checked, redacted conversation results. It requires explicit permission
for real test writes. Command: `docker compose --profile evaluation run --rm --build eval-agent`.
An empty `/eval-dashboard` does **not** mean evaluations passed.

**The optional legacy read-only MCP smoke runner** requires 3 separately issued valid OAuth tokens (`EVAL_CITIZEN_A_TOKEN`, `EVAL_CITIZEN_B_TOKEN`, `EVAL_OFFICER_TOKEN`) and configured fixture identities. Run it only after those tokens exist.

## F. Day-to-day operation

```bash
cd ~/sevasetu/sewasetu-ai-handout
sudo docker compose ps
sudo docker compose logs -f --tail=60 app proxy
sudo docker compose restart app
# Enable Docker across reboots:
sudo systemctl enable docker
# Stop without deleting PostgreSQL or upload volumes:
sudo docker compose down
# Restart:
sudo docker compose up -d
# Backup database (inside project directory as private-backups):
sudo bash deploy/backup.sh
```

**Backups:** database backups do not include uploaded documents. Export the uploads Docker volume separately, protect the backups and periodically test restoring to a separate database. For AWS credit expiration, copy backups off EC2.

## Privacy, demo readiness and limits

- `seed/seed.sql` in the supplied handout claims to be a *production data export* containing names, mobile numbers, and bank-account-like data. No proof of authorization or synthetic status was provided. **The default public deployment does not import it.** The original is retained inside the archive for source parity and must not be used for live internet hosting unless explicitly authorized.
- This is a simulated SMS gateway, **not real SMS delivery**. Public citizen users cannot reliably receive OTPs. For evaluators, provide a safe authorized demo OTP process; do not weaken OTP or expose its inbox.
- The project's original scheme application deadline is **2026-10-31**. The portal will reject new applications after that date unless the assignment supplies an authorized extension. Do not silently alter legal/business rules.
- This bundle has had source/static checks only, not a live Docker/EC2 end-to-end verification. HTTPS, Postgres, OAuth, upload and MCP behavior must be checked after deployment.
- Free Tier eligibility does not guarantee zero AWS charges. Review the active AWS plan and credit balance.
