# Seva Setu: Defect fixes and live evaluation implementation

October 23, 2026. This archive is an edited copy of `sewasetu-aws-complete-latest(1).zip`, not a replacement for the original handout.

## Confirmed fixes

| Defect | Change | Regression guard |
|---|---|---|
| Missing age-proof ticket template | Created `app/templates/mcp_document_ticket.html`; protected ticket display by OTP-verified session, CSRF-protected POST and `Cache-Control: no-store` for both GET and POST | File exists, template/form structure reviewed |
| MCP 2 Python SDK result field mismatch | Changed `isError` to `is_error` and `structuredContent` to `structured_content` in `app/eval_client.py` | `tests/test_eval_agent.py` verifies error/success conversion |
| Officer queue eval false failures | Added explicit `status: PENDING` in `app/mcp_actions.py` queue output | Existing `tests/test_step5_evaluation.py` validates status expectation |
| OAuth connected-apps revocation malformed HTML | Rebuilt `app/templates/connections.html` with two properly paired forms and CSRF tokens for individual and bulk sign-out | Two form openings/closings and two CSRF fields verified |
| MCP 2/PyJWT dependency mismatch | Updated `PyJWT[crypto]>=2.10.1,<3` in `app/requirements.txt` | SDK v2 dependency requirement checked against published documentation; fresh image resolution still needs deployment test |

## Actual agent evaluation workflow

New `app/eval_agent.py` is the **canonical, real** evaluation runner: connects to real HTTPS MCP resource servers, runs a configured OpenAI-compatible tool-calling model, records tool names and redacted conversation turns, verifies database state with the portal's PostgreSQL verifier, and publishes authentic results. Write scenarios are gated by an explicit environment value and a small, untouched demo-fixture check. Six fictional personas/scenarios are included in `app/evaluation/cases.example.json` and explained in `app/evaluation/README.md`.

This runner is connected to Docker Compose under the optional `eval-agent` profile and publishes to the existing public `/eval-dashboard` volume. `app/eval_public.py` displays only tagged `live_agent_db_verified` reports. The old direct MCP smoke runner remains private. The old DB-only verifier is marked `manual_db_only` and its output is not mistaken for real AI conversations.

## Verified offline

- Python syntax parsed for all 30 Python sources in the edited project.
- Docker Compose file parsed as valid YAML, with 11 services, including the evaluation service.
- `connections.html` now has matched opening and closing forms and CSRF fields.
- New ticket template exists and references the original session-verified flow.
- **26 Python unit tests passed** in offline test conditions: existing submission and repository tests, existing response-shape tests, and new evaluation workflow logic. For the tests requiring the MCP/HTTP/PostgreSQL modules, the offline harness used stub modules: this **does not** demonstrate those packages are installed or that real network/database traffic succeeds.

## Still requiring the deployment, credentials and human review

- A real Docker image build and dependency installation against the pinned requirements.
- A real OAuth authorization flow for two synthetic citizens and an officer; a valid age-proof ticket after OTP verification.
- A real LLM capable of tool calling, actual HTTPS MCP connections and the live PostgreSQL demo database.
- A full run, its genuinely generated report, and review of public redaction before sharing `/eval-dashboard`.
- Host uptime, external reviewer sign-in, Loom, private Git history, and the one-page design note.

No real agent conversations were executed in this sandbox and no success percentages or transcripts were manufactured. Follow `app/evaluation/README.md` to run the end-to-end evaluation safely and finish those deployment-dependent checks.
