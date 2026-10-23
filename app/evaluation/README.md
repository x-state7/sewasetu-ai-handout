# Seva Setu: genuine AI-agent evaluations with PostgreSQL proof

The original assignment requires **real assistant conversations** made through a **real MCP client** followed by actual checks against the portal's PostgreSQL database. `eval_agent.py` implements that pipeline. It does not fabricate successful transcripts or pre-populate the public evaluation dashboard.

## 1. Isolation and requirements

Run only against a disposable, **synthetic** test database. Before write-enabled runs the evaluator refuses databases larger than 200 applications or missing the expected untouched demo application fixtures (`DEMO000001`, `DEMO000002`, `DEMO000008`). The included `seed/demo-seed.sql` has known fictional application references `DEMO000001`...`DEMO000012`. Do **not** evaluate with the supplied production-labelled `seed/seed.sql` without explicit authorization. The test deliberately changes records; restore/reset the demo database before repeating it. An empty public dashboard is expected until a real evaluation finishes.

The default scenario order is intentional: one citizen reads their pending case; another verifies cross-citizen isolation; the first withdraws their pending case; the officer approves and rejects two assigned-block cases; the second citizen resubmits following rejection. The scripted dialogues express genuine user goals, while a configured LLM selects and invokes tools; the results are **not** hardcoded.

You need three genuinely authenticated, distinct OAuth access tokens:

- `EVAL_CITIZEN_A_TOKEN`: authenticated citizen mobile **0000000001** (fixture only).
- `EVAL_CITIZEN_B_TOKEN`: authenticated citizen mobile **0000000002** (fixture only).
- `EVAL_OFFICER_TOKEN`: officer authorized for **Sonari** and **Rajapara**.

Obtain tokens using the portal's OAuth authorization-code / PKCE sign-in flow (or a properly authorized officer program token), not by hand-crafting JWTs. Token scopes, subjects and resource audiences must match each MCP endpoint. OAuth tokens expire; refresh/reissue them immediately before the run. Store them only in your private `.env`; never in Git, user-visible screenshots, reports or messages.

The submission test also needs an **unused one-time age-proof ticket** issued through the OTP-verified `/mcp/age-proof` then `/mcp/document-ticket` route while signed in as **0000000002**. Upload a synthetic JPG/PNG/PDF document; copy the one-time ticket into C04 in `private-eval/cases.private.json`. The application deadline defined by this project is October 31, 2026; submission tests after it will correctly fail unless the authorized scheme rules change.

## 2. Configure private evaluation cases

From the project root:

```sh
cp app/evaluation/cases.example.json private-eval/cases.private.json
chmod 600 private-eval/cases.private.json
```

Each case specifies fictional identity (name, age, village, speaking style and goal), one or more user turns, required MCP tools, assertions about tool results, the expected application/database owner/status/audit, and a `mutation` flag. The only item to replace in C04 is its `REPLACE_WITH_FRESH_ONE_TIME_TICKET_FROM_PORTAL` placeholder; update `private_redactions` accordingly. You may change any fictional persona details for your own realistic tests.

For **read-only smoke tests**, remove the cases with `mutation: true` (C03, O01, O02, C04) and leave writes disabled. These read-only runs will still check live MCP access and actual PostgreSQL state, but they do **not** demonstrate that the AI can submit/withdraw/decide cases.

For **full evaluation**, use a fresh demo database and the complete six cases (writes are real). Do not let an assistant access production records or real banking data.

## 3. Configure model and run

Add these private keys to your deployment `.env` (already listed in `.env.example`):

```dotenv
EVAL_CITIZEN_URL=https://YOUR_DOMAIN/mcp/citizen
EVAL_OFFICER_URL=https://YOUR_DOMAIN/mcp/officer
EVAL_CITIZEN_A_TOKEN=...
EVAL_CITIZEN_B_TOKEN=...
EVAL_OFFICER_TOKEN=...
EVAL_LLM_BASE_URL=https://YOUR_OPENAI_COMPATIBLE_PROVIDER/v1
EVAL_LLM_MODEL=YOUR_TOOL_CALLING_MODEL
EVAL_LLM_API_KEY=...
# ENABLE ONLY against a disposable, private, synthetic database
EVAL_ENABLE_WRITES=YES_I_AUTHORIZE_SYNTHETIC_TEST_WRITES
```

The LLM endpoint must support `POST /chat/completions`, `tools` and `tool_calls` (OpenAI-compatible API). An operator-owned, private HTTP model (e.g. an isolated Ollama compatible `/v1` endpoint on the Docker network) is supported only with `EVAL_ALLOW_INTERNAL_LLM_HTTP=YES`. This flag must **not** be used for untrusted Internet endpoints.

Run from the project root, with Docker services already running:

```sh
docker compose --profile evaluation run --rm --build eval-agent
```

The container reads `./private-eval/cases.private.json` from a **read-only volume**, without incorporating it into the Docker image. DB access is read-only *for the evaluator itself*; writes can occur only through the live MCP tools. The eval-agent accesses real Streamable HTTP MCP resources over HTTPS and calls the configured model. The public report is written to the `evalpublic` Docker volume for `/eval-dashboard`. Do not use demo outputs as if they were real runs.

## 4. What is checked

Each evaluation stores the public fictional persona, stated goal, redacted citizen/officer and assistant messages, the names of MCP tools actually called (not arguments), the database-check outcome and a pass/fail/error status. The private evaluation runner checks:

1. MCP tool advertisement is role-separated; the client uses the configured real bearer token and endpoint.
2. Required tools were actually invoked, and optional tool response assertions were met.
3. PostgreSQL identifies the expected application owner, status and age-proof, required audit action, and active-application count (if specified).
4. For a mutation scenario, the expected database state **changed relative to its pre-conversation snapshot**; for a read-only case, the targeted state is unchanged.
5. The public dashboard only loads `mode=live_agent_db_verified` reports. Legacy DB-only verifier outputs are **not** presented as proof of an assistant conversation.

Because this is an external model test, some models may not call the intended tools. Such a run should honestly be marked FAIL or ERROR, not manually changed to PASS. Check the private run's errors, refine instructions or case dialogue, rerun against fresh fixtures and document what changed in your Loom.

## 5. Limits and security notes

- **No actual test has been executed by merely creating these files.** Only the deployed host has tokens, model connectivity and the real DB needed to produce genuine results.
- Never publish raw user/assistant tool arguments or response payloads. `eval_agent.py` exposes only redacted user and assistant prose plus tool names. The public report limits length and redact sensitive-looking tokens, bank identifiers and mobile numbers. Human-review public transcripts before distributing URLs.
- The script does not generate or bypass OTPs or create fake OAuth tokens. The citizen must complete portal verification and authorization legitimately.
- Write-enabled runs require fresh, untouched demo fixtures and will refuse a second run against already-mutated fixtures. Reset the demo Postgres and upload volumes safely before reruns; `docker compose down -v` is destructive and **must not** be run against a valued deployment. Prefer a dedicated disposable test stack/database.
- Token expiry, HTTPS, real model quality and live Docker routing must be verified on the deployment. Zero PASS is a legitimate outcome and should remain visible for debugging.
- The original read-only runner (`app/eval_runner.py`) and manual SQL verifier (`app/eval_verify.py`) remain available for diagnosis but are **not** the complete AI-conversation evidence required by the handout.
