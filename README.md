# SevaSetu — Agent-Ready Pension Portal

**Build for Bharat Fellowship 2027 · AI Track · Take-home assignment**  
**Deployment:** [SevaSetu production portal](https://sevasetu-internship.duckdns.org/)  
**Evaluation:** [Live, database-verified MCP evaluation dashboard](https://sevasetu-internship.duckdns.org/eval-dashboard)

> **Assessment summary (verified on the public dashboard on 31 October 2026):** The newest six-case evaluation, `eval-0fce4933650542d9b03b1ebda164d459`, passed **6/6 (100%)** using `gemini-3.5-flash-lite`, authenticated MCP tools, and PostgreSQL assertions against an **isolated 12-record synthetic staging database**. Earlier failure reports remain visible and are not retroactively changed. This is a test result, not a guarantee of passing independent assessor scenarios.

## 1. Problem and approach

The supplied SevaSetu portal is a fictional government old-age pension service. Citizens authenticate by mobile OTP, provide their details and age proof, and receive an application number. Block officers review applications and approve or reject them. A separate 15-day rule provides for deemed approval if no decision is made.

The objective was to let a real AI assistant operate the service **through an authorized, auditable channel**, without replacing the portal or giving the model powers that the human-facing service would not grant. This project adds two distinct **Model Context Protocol (MCP) Streamable HTTP** endpoints:

- **Citizen MCP:** scheme guidance, authenticated citizen application status, withdrawal, and eligible new submissions.
- **Officer MCP:** officer-scoped application lookup/queue review and approve/reject operations with recorded decisions.

The **Flask portal + PostgreSQL** remain the system of record. A simulated SMS gateway supports the fictional demonstration identities.

## 2. Public assessment URLs

| Service | URL |
|---|---|
| **Portal** | https://sevasetu-internship.duckdns.org/ |
| **Citizen MCP (Streamable HTTP)** | https://sevasetu-internship.duckdns.org/mcp/citizen |
| **Officer MCP (Streamable HTTP)** | https://sevasetu-internship.duckdns.org/mcp/officer |
| **Admin portal** | https://sevasetu-internship.duckdns.org/admin |
| **Restricted synthetic OTP login** | https://sevasetu-internship.duckdns.org/reviewer/otp/login |
| **Synthetic OTP viewer (authenticated)** | https://sevasetu-internship.duckdns.org/reviewer/otp |
| **Evaluation dashboard** | https://sevasetu-internship.duckdns.org/eval-dashboard |
| **OAuth discovery** | https://sevasetu-internship.duckdns.org/.well-known/oauth-authorization-server |

**Important:** `/mcp/citizen` and `/mcp/officer` are protocol endpoints, not web pages. An unauthenticated browser or `curl` request may return `401`; that is normal for OAuth-protected MCP servers. Confirm the endpoints with an OAuth-capable MCP client, not by expecting an ordinary HTML page.

## 3. Architecture

```text
                       Independent MCP clients
                       (Claude Code / Gemini CLI)
                            |             |
                       OAuth login   OAuth login
                            |             |
            /mcp/citizen --+             +-- /mcp/officer
              (citizen tools)               (officer tools)
                            \             /
                          Server-side actions
                         / shared validation \
                       Flask portal and auth
                                 |
                   PostgreSQL + audit trail
                         (system of record)

 Browser (OTP-verified) ---- Flask portal
               |                 |
    Restricted synthetic      upload + one-use
    OTP reviewer viewer       proof ticket

 HTTPS reverse proxy publishes portal, MCP, OAuth discovery and evals.
 Synthetic SMS gateway is used for the demo; scheduled jobs enforce time rules.
```

Design properties:

1. **Separate authorization surfaces:** a citizen's MCP tool list does not expose officer functions. Identity comes from verified OAuth, not mobile numbers invented by the model. Officer operations are constrained by their authorized blocks.
2. **Existing validation remains authoritative:** the portal and agent share server-side business rules (age, block, required fields, deadline, approval context). A convincing AI answer does not count as a completed transaction.
3. **Proof and transaction integrity:** verified uploads use one-use, time-limited document tickets; only a hash is stored. Application insertion and ticket consumption are coupled in PostgreSQL.
4. **Auditable actions:** application status changes and actor/reason details are recorded for review.
5. **Outcome-based evaluations:** a real LLM calls authenticated MCP tools; checks inspect actual PostgreSQL state, not merely assistant prose.

## 4. Independent assessor — start here (no EC2 access needed)

The official submission form provides the **assessor admin username and password** for the portal. **No production `.env`, SSH key, PostgreSQL password, Gemini API key, OAuth signing key or long-lived access token is required** to use the hosted MCP endpoints.

### 4.1 Connect Claude Code

In a terminal on the assessor's own machine, with Claude Code installed and signed in:

```bash
claude mcp add --transport http sevasetu-citizen \
  https://sevasetu-internship.duckdns.org/mcp/citizen

claude mcp add --transport http sevasetu-officer \
  https://sevasetu-internship.duckdns.org/mcp/officer

claude mcp list
claude
```

Inside Claude Code, use `/mcp` to inspect connections and complete OAuth authentication when prompted. **Authenticate the two servers as their intended different roles.** For a citizen-only test, disable the officer connection or use a separate profile/session; do not combine identities when checking authorization separation.

Claude Code reference: https://code.claude.com/docs/en/mcp

### 4.2 Alternative: Gemini CLI

Gemini was used for the submitted automated evaluations; the server does not depend on Gemini itself. Gemini CLI can also connect through HTTP:

```bash
gemini mcp add --transport http sevasetu-citizen \
  https://sevasetu-internship.duckdns.org/mcp/citizen

gemini mcp add --transport http sevasetu-officer \
  https://sevasetu-internship.duckdns.org/mcp/officer

gemini
```

Inside Gemini CLI, use `/mcp auth sevasetu-citizen` or `/mcp auth sevasetu-officer` as needed. Client/provider accounts are the assessor's own; **the server operator's model API key is not required**. See https://geminicli.com/docs/tools/mcp-server/.

### 4.3 Citizen OAuth and synthetic OTP

Test identities configured for the restricted reviewer OTP viewer include:

| Persona | Fictional mobile | Scenario |
|---|---|---|
| **Madhabi Das** | `0000000001` | Own application lookup, explicit withdrawal |
| **Salim Ali** | `0000000002` | Privacy denial, reapplication after rejection |
| **Officer demo case** | `0000000008` | Officer queue and decision exercises |

To authenticate:

1. Start **Citizen MCP** OAuth from the client and enter an authorized fictional mobile, for example `0000000001`.
2. Request the one-time code; the simulator delivers it to the internal SMS gateway, not to a real phone.
3. In another browser tab, open [restricted OTP login](https://sevasetu-internship.duckdns.org/reviewer/otp/login).
4. Log in using the **approved reviewer OTP access method**. The default code supports a separate `REVIEWER_OTP_USERNAME` / `REVIEWER_OTP_PASSWORD` account. An administrator login accesses the viewer **only if the optional admin-to-viewer authorization change is actually deployed**. The maintainer must verify and arrange one of these methods **before inviting independent assessors**.
5. Select the same allowlisted synthetic mobile number. Once delivered, read the displayed OTP; enter it in the **original citizen OAuth** screen and approve consent.
6. Ask: **“Please list my pension applications and tell me their status.”**
7. Try a cross-citizen lookup: it must not reveal another person's application.

The OTP viewer must never be treated as an unrestricted SMS inbox, must remain protected by authentication, and must only allow explicitly listed synthetic mobiles. A code may expire or be consumed; request a fresh code through the normal flow. **The credential delivery route for the OTP viewer must be explicitly confirmed by the maintainer; the official form alone does not contain a separate field for it.**

### 4.4 Officer OAuth

1. Connect to the **Officer MCP** endpoint, initiate OAuth and log in with the authorized assessor officer credentials. The configured dedicated `OFFICER_REVIEWER_*` login is **not the same as the portal admin account**, although the deployed OAuth implementation may additionally accept the portal admin identity for officer OAuth.
2. Ask: **“Show the pending pension applications for my authorized block.”**
3. Request details and current status for a permitted test case.
4. When appropriate, explicitly confirm approval/rejection with a reason; verify the changed status and audit record in the portal.
5. Never assume a recorded evaluation's former `PENDING` fixture is still pending in the production database. These operations mutate state; inspect it first.

**Assessor access preflight:** The maintainer must verify that the form-provided portal admin credential can log in, the OAuth officer credential can authorize, and an external reviewer can actually obtain a synthetic citizen OTP without SSH or operator intervention. If the reviewer OTP login uses a separate password, it must be delivered privately by an authorized channel; do not put credentials in Git.

## 5. Suggested acceptance tests

| Workflow | Expected server-side outcome |
|---|---|
| Citizen reads own application | Only records owned by authenticated mobile returned |
| Citizen tries someone else's reference | Denied or hidden, with no cross-account disclosure |
| Citizen withdraws pending application | Only with explicit confirmation; database status updated and audited |
| Officer lists/checks assigned queue | Only authorized block records accessible |
| Officer approves or rejects | Explicit confirmation, stored reason/actor, portal and database agree |
| Citizen submits pension request | Valid details, verified age proof, fresh one-time ticket, eligible application window; returns a new reference and `PENDING` status |

**Scheme deadline:** The original configured new-application cutoff is **31 October 2026, 23:59 IST**. After it, a legitimate request may be rejected because the window is closed. Do not alter the server clock, silently disable this validation, or misrepresent that refusal as a successful application. The fellowship's assessment may run later than the scheme window.

## 6. Real-agent evaluation evidence

The public dashboard is at **https://sevasetu-internship.duckdns.org/eval-dashboard**. The newest verified full run is:

| Field | Value |
|---|---|
| Run ID | `eval-0fce4933650542d9b03b1ebda164d459` |
| Run timestamp | 2026-10-31 16:02:13 UTC |
| Model | `gemini-3.5-flash-lite` |
| Method | Live LLM + authenticated MCP calls + PostgreSQL assertions |
| Environment | Isolated synthetic staging (12 initial applications) |
| Result | **6 PASS / 0 FAIL / 0 ERROR — 100%** |

| Case | Persona / objective | Verified result |
|---|---|---|
| C01 | Madhabi Das: reads own pending application | PASS |
| C02 | Salim Ali: attempts cross-citizen read | PASS (access not disclosed) |
| C03 | Madhabi Das: explicitly withdraws own application | PASS |
| O01 | Officer Priya: checks and approves an authorized case | PASS |
| O02 | Officer Priya: checks status then rejects with reason | PASS |
| C04 | Salim Ali: submits a new application using verified age-proof ticket | PASS |

Historical reports were preserved, including unsuccessful trials. They informed targeted fixes: a missing officer status check before rejection, a PostgreSQL INSERT-placeholder mismatch, and a mismatched document-ticket value across staging fixture resets. The **6/6** score pertains to these six known synthetic cases; the independent reviewer may invent new cases and obtain different results.

**Repeatability:** The write-enabled six-case suite is designed for a disposable staging database. It starts from a 12-row fixture, needs three separate OAuth identities and a fresh verified age-proof ticket, and changes application records. Do **not** run write evaluations or `docker compose down -v` against production. Private case prompts containing tickets, tokens, bank fields, and uploaded proof are intentionally not checked into the repository.

## 7. Run the code yourself (source installation)

**Prerequisites:** Docker Engine, Docker Compose v2, Git, and either an appropriate HTTPS hostname/reverse proxy for live OAuth testing or a verified local development configuration. The production deployment uses an Ubuntu EC2 VM, Docker Compose, Flask, PostgreSQL, two MCP services, the simulated SMS gateway and a HTTPS reverse proxy.

```bash
# Clone only after the reviewer is granted access to the private repository:
git clone REPLACE_WITH_PRIVATE_GITHUB_REPOSITORY_URL
cd sewasetu-assistant

# Create your OWN environment file from non-secret placeholders:
cp .env.example .env
chmod 600 .env

# Edit .env with NEW local credentials, public origin and OAuth settings.
# Do NOT paste the hosted EC2 .env into a checkout.
${EDITOR:-nano} .env

# Validate configuration, inspect services, and start:
docker compose config --quiet
docker compose config --services
docker compose up -d --build
docker compose ps
```

**Fresh-clone caveat:** Before claiming a one-command deployment, verify that this exact revision's Compose setup correctly mounts `app/schema.sql`, the intended **sanitized** seed, and any necessary migrations; confirm its exposed ports and proxy/TLS behavior. PostgreSQL initialization scripts execute only on a fresh empty database volume. A local Docker start **does not automatically reproduce externally reachable OAuth redirect URLs**, and the assessment's public endpoints should be used when testing from an independent client's machine.

Useful diagnostics:

```bash
docker compose config --services
docker compose ps
docker compose logs --tail=80 app mcp-citizen mcp-officer
```

The source includes a deployment helper at `deploy/generate_aws_env.py` in the reviewed patch. Inspect that script and its expected domain argument **before** invoking it; do not run it on an existing deployment or assume it has a `--help` mode. Never overwrite an existing production `.env`, delete production PostgreSQL volumes, or publish secret-bearing fixtures in order to get a local demonstration working.

### Reviewer access variables (documented in `.env.example`)

These are **variable names**, not values to commit:

| Variable | Purpose |
|---|---|
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Portal administrator; may support officer OAuth in deployed implementation |
| `OFFICER_REVIEWER_USERNAME`, `OFFICER_REVIEWER_PASSWORD` | Separate officer-only reviewer OAuth account |
| `REVIEWER_OTP_USERNAME`, `REVIEWER_OTP_PASSWORD` | Restricted synthetic OTP viewer account |
| `REVIEWER_OTP_MOBILES` | Explicit whitelist of fictional mobiles |
| `PUBLIC_BASE_URL`, `PUBLIC_HOSTNAME` | Public HTTPS origin and hostname |
| `DB_PASSWORD`, `SECRET_KEY` | Private database and session secrets |
| `EVAL_LLM_API_KEY` | Private key only for the optional automated evaluation runner |

The actual `.env.example` should be cross-checked with this release's Compose file to ensure *all* required variables are covered.

### Read-only production health checks (operator)

```bash
cd ~/sevasetu/sewasetu-ai-handout
sudo docker compose ps
sudo docker compose exec -T db psql -U sewasetu -d sewasetu \
  -c 'SELECT COUNT(*) AS applications FROM applications;'
python3 deploy/submission_preflight.py
```

These operator commands require EC2 access and are **not** necessary for an external MCP assessment. Do not start the 15-day scheduler purely to demonstrate the system: it can modify production records.

## 8. Security, limitations, and operational notes

- OTP delivery is a simulated, reviewer-restricted workflow, not real carrier SMS.
- Reviewer OTP access is a limited test helper, **not** a bypass of citizen OTP validation.
- Role separation is enforced on server endpoints. Never give a citizen officer credentials.
- The age-proof ticket is bound to the verified mobile, has a limited lifetime (30 minutes in the tested implementation), and is consumed after successful submission.
- Scheme deadlines, block authorization and other portal validations are authoritative, including for AI agents.
- **Assessment caveat:** earlier evaluation evidence surfaced a potential officer approval of a legacy fixture without age proof. This needs independent business-rule review; a 6/6 evaluation of the listed cases is not a comprehensive policy audit.
- Data in this exercise is fictional/simulated. Do not use real citizen identity documents, live phone numbers or bank details.
- Keep the production site available through the assessment period specified in the fellowship form (approximately 30 days after submission deadline unless notified earlier).

## 9. Repository map and documentation

Common paths in this project revision:

```text
sewasetu-assistant/
├── README.md                 # this file
├── REVIEWERS.md              # reviewer access notes, no credentials
├── DESIGN_NOTE.md            # required one-page design reflection
├── BRIEF.md                  # original project brief, if retained
├── .env.example              # placeholders only, never credentials
├── docker-compose.yml
├── app/                      # Flask portal, OAuth, MCP actions, evaluation logic
├── deploy/                   # infrastructure and preflight helpers
├── seed/                     # synthetic seed fixtures (review before publishing)
└── tests/                    # security and regression tests
```

The submission brief additionally requests the **private repo named `sewasetu-assistant` with original Git history**, reviewer `harshnisar` invited, **a ZIP containing `.git`**, the public portal and MCP endpoints, the `/eval-dashboard` URL, assessor portal credentials through the **official form**, a **face-and-screen Loom under three minutes**, and a one-page design note explaining three design choices and one thing to change with more time.

**Never commit `.env`, API keys, passwords, SSH keys, OAuth tokens, document tickets, private evaluation cases, database dumps, or unreviewed personal data.** Git history and the ZIP must be checked as well as the current working tree.

---

**Before handing this README to reviewers:** confirm the OTP credential-delivery path, test both OAuth logins from a fresh external machine, verify the actual source clone/Compose configuration, add the final private GitHub URL, and check that all submission URLs remain reachable.
