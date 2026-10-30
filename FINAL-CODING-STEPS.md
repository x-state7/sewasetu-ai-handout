# SevaSetu — coding patch instructions for the supplied October 30 ZIP

This is a **narrow patch** for the pre-existing, working SevaSetu application. It is
**not a replacement for the actual running EC2 source**. Preserve your newer live
changes, especially the MCP list-normalization fix and any reports, before
merging. The supplied ZIP had an uncommitted change in each Dockerfile; do not
overwrite these blindly.

## What changed (new vs updated)

| File | Change | Reason |
| --- | --- | --- |
| `app/reviewer_access.py` | NEW | Separate reviewer officer OAuth credentials; strict synthetic OTP whitelist and parsing |
| `app/templates/reviewer_otp_login.html` | NEW | Reviewer-only login form with existing CSRF validation |
| `app/templates/reviewer_otp.html` | NEW | Select a fictional mobile and read only the latest delivered OTP |
| `app/oauth.py` | UPDATED | Use `officer_subject()` for OAuth; reviewer officer **never** becomes portal admin |
| `app/app.py` | UPDATED | `/reviewer/otp/login`, `/reviewer/otp`, `/reviewer/otp/logout`; no-store headers |
| `docker-compose.yml` | UPDATED | Pass reviewer environment variables **only** to Flask app |
| `.env.example` | UPDATED | Document all reviewer settings; no actual credentials |
| `deploy/generate_aws_env.py` | UPDATED | Generate safe reviewer secrets for fresh installs |
| `deploy/add_reviewer_env.py` | NEW | Append randomly generated reviewer credentials to an existing private `.env` |
| `seed/eval-seed.sql` | NEW | Synthetic names match personas and pending dates are current when DB initialized |
| `tests/test_reviewer_access.py` | NEW | Offline credential, OTP security and Flask route regression tests |
| `deploy/submission_preflight.py` | NEW | Read-only submission checks; warns on secret/data risks |

**No database schema migration is required for this patch.** The officer and
reviewer login roles are configured independently; they do not add tables.

## 1 — Preserve the actual running EC2 state

On EC2, **before copying anything over the existing project**:

```bash
cd ~/sevasetu/sewasetu-ai-handout
sudo bash deploy/backup.sh
sudo ls -lh private-backups/
git status --short
git log -1 --oneline
```

Preserve existing `private-eval/evidence/` and the running `.env`. No step in
this patch requires deleting or resetting your production Postgres volume.

## 2 — Apply the patch to the same source version

Unzip the supplied patch **over a clean copy** of the *same* project version,
reviewing `git diff` before shipping to EC2. If the live EC2 project has
additional changes, merge the changed files rather than wholesale overwriting.

Updated files: `app/app.py`, `app/oauth.py`, `docker-compose.yml`,
`.env.example`, and `deploy/generate_aws_env.py`. Copy in the *new* files too.
Keep the existing `.env`, `private-eval`, Git history and original Dockerfiles.

## 3 — Add secure reviewer credentials to the EXISTING `.env`

From the project root on the actual EC2 server after applying the patch:

```bash
python3 deploy/add_reviewer_env.py
chmod 600 .env
```

This helper generates and appends missing `OFFICER_REVIEWER_USERNAME`,
`OFFICER_REVIEWER_PASSWORD`, `REVIEWER_OTP_USERNAME`,
`REVIEWER_OTP_PASSWORD`, and `REVIEWER_OTP_MOBILES`. It does **not** print the
passwords and does not overwrite your existing passwords or tokens. For a fresh
staging VM, `python3 deploy/generate_aws_env.py STAGING-DOMAIN` generates these
secrets when creating its new `.env`.

For the default synthetic database, the OTP viewer only supports mobiles
`0000000001`, `0000000002`, and `0000000008`. It is intentionally not an open
SMS console. **Never include genuine citizens' mobile numbers in this list.**

## 4 — Rebuild *only* the Flask application container

```bash
sudo docker compose config --quiet
sudo docker compose up -d --no-deps --build app
sudo docker compose ps
sudo docker compose logs --tail=60 app
```

The MCP containers, database, scheduler, dashboard and proxy do not need to be
recreated for these reviewer login changes. If the latest live Dockerfiles or
other runtime code differ, test in staging first.

## 5 — Test officer OAuth login and synthetic OTP access

1. Perform a real OAuth officer authorization-code/PKCE sign-in through the MCP
   client, using `OFFICER_REVIEWER_USERNAME` and
   `OFFICER_REVIEWER_PASSWORD`. It must issue an `officer:` subject, offer only
   officer tools, and honor `OFFICER_ALLOWED_BLOCKS`.
2. Confirm the same reviewer officer password does **not** grant access at
   `/admin` or `/admin/dashboard`.
3. In a separate browser, sign in to `/reviewer/otp/login` using
   `REVIEWER_OTP_USERNAME/PASSWORD` from the private `.env`.
4. Start a normal **citizen** OAuth or status login for synthetic mobile
   `0000000001`; request an OTP. On the reviewer page select that mobile;
   after simulated delivery (1–4 seconds), the six-digit code appears.
5. Complete the original citizen OTP verification and OAuth consent as usual.
6. Check that a mobile outside the whitelist is rejected; logout should
   revoke access to the reviewer-only page. Do not expose `/__gateway/`.

Run the **offline tests** in an isolated local Python environment with the
`app/requirements.txt` dependencies installed, or mount tests into a one-off
container using the already built app image:

```bash
sudo docker compose run --rm --no-deps -v "$PWD/tests:/app/tests:ro" \
  app python -m unittest discover -s /app/tests -p 'test_reviewer_access.py' -v
```

These tests do not intentionally connect to or mutate the production database;
the Flask test client mocks the SMS gateway and checks authentication only.

## 6 — Prepare a separate synthetic write-evaluation staging stack

**Never use the same Docker project or PostgreSQL volume as production.** On
an isolated staging VM with its own HTTPS hostname and an unused Postgres
volume, use `SEVASETU_SEED_FILE=./seed/eval-seed.sql` in the staging `.env`.
This seed differs from the original: Madhabi Das and Salim Ali are named
correctly, and pending demo rows use the initialization time so the nightly
15-day SLA does not immediately deem them approved.

Use the existing six-case `app/evaluation/cases.example.json` and perform the
C04 synthetic age-proof upload before the AI run. Use fresh, staging-specific
citizen A, citizen B and reviewer officer OAuth tokens, the actual configured
LLM, and explicit write authorization **only on staging**:

```dotenv
EVAL_ENABLE_WRITES=YES_I_AUTHORIZE_SYNTHETIC_TEST_WRITES
```

```bash
cp app/evaluation/cases.example.json private-eval/cases.private.json
chmod 600 private-eval/cases.private.json
sudo docker compose --profile evaluation build eval-agent
sudo docker compose --profile evaluation run --rm eval-agent
```

This should produce **real**, auditable results for C01, C02, C03, O01, O02,
C04; a pass is not guaranteed. Check PostgreSQL status changes and audit logs
and retain the output. The project's **scheme deadline is 2026-10-31 23:59 IST**;
late C04 submissions must correctly fail rather than overriding business rules.

## 7 — Verify and preserve genuine evaluation reports

The live AI runner writes a UUID-named JSON report into the `evalpublic` Docker
volume. The public dashboard exposes it at `/eval-dashboard`. To preserve the
older successful 3/3 report without rerunning Gemini, inspect the correct
volume on EC2 and copy the existing JSON file only if present:

```bash
sudo docker volume ls --format '{{.Name}}' | grep evalpublic
# Replace VOLUME below with the exact name from that listing.
sudo docker volume inspect VOLUME --format '{{.Mountpoint}}'
```

Never substitute a synthetic report or edit a failure to PASS. The full run
from staging must be clearly identified as a staging/synthetic run when
publishing reviewed, redacted evidence to the public dashboard.

## 8 — Check before producing the repo ZIP

```bash
python3 deploy/submission_preflight.py
python3 -m compileall -q app deploy tests
```

Commit the selected source changes without `.env`, private evidence, OAuth
secrets or API keys. Review the already-tracked `seed/seed.sql`: it is a
large production-labeled export supplied with the starter repo. Determine
whether it is actually synthetic/authorized before redistribution. An ignored
file that was committed in earlier Git history remains in that history.

The brief requires a private GitHub repo **`sewasetu-assistant`** with genuine
history and `harshnisar` invited, as well as a ZIP including `.git`. Preserve
legitimate existing history; do not fabricate it. Separately complete the
three-minute Loom and one-page design note.
