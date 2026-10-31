# SevaSetu — Design note
**Build for Bharat AI track | One-page design reflection**

## The problem and who I designed for

The pension portal is difficult for older citizens using shared phones, assisted kiosks, or a relative's device. An AI assistant should guide them through **the same service** they would access at the counter, not create an easier route around eligibility, identity checks, or administrative authority. My test personas include **Citizen A**, whose own application must remain private; **Citizen B (Salim Ali, Rajapara)**, whose prior application was rejected and who needs to apply again with an age-proof document; and a **block officer** who needs to inspect the queue, act on cases, and record decisions. An adversarial cross-account read is included to check access boundaries.

## Three decisions that mattered most

**1. Separate MCP surfaces by authority.** I exposed two distinct Streamable HTTP endpoints, `/mcp/citizen` and `/mcp/officer`, protected through OAuth. Citizen tools operate on the authenticated citizen's identity, not an arbitrary mobile number asserted by the model. An officer's queue and decision tools are accessible only through the officer surface. This limits the damage of an AI mistake or a malicious instruction.

**2. Keep the portal and PostgreSQL as the source of truth.** Rather than let the LLM invent a decision or bypass validation, MCP operations call the same business rules as the Flask portal. Pension applications validate eligibility and required data; the verified portal issues short-lived, one-use document tickets. Submission and ticket consumption are coordinated transactionally. Officer decisions and the 15-day deemed-approval policy belong in server-side rules and the audit trail, not in the model's prompt.

**3. Evaluate conversations by database outcomes, not fluent text.** Six synthetic scenarios exercise citizen self-service, cross-user denial, withdrawal, officer approval, officer rejection, and new submission. A real LLM client calls the MCP servers, and checks compare the resulting PostgreSQL state with case expectations. Earlier evaluations revealed a missed officer status lookup, an SQL insertion issue, and a mismatched/expired document-ticket risk. The fixes targeted those specific failure modes; historical failures are preserved rather than rewritten.

## What I would change with more time

I would automate the **entire disposable evaluation fixture lifecycle**: safely initialize the 12-case staging database, create role-scoped short-lived OAuth sessions, issue a new synthetic proof ticket, run the six conversations, and record a signed audit/evidence bundle. Manual ticket refresh and database resets created avoidable fragility and are not representative of a sustainable test process. I would also user-test the conversational flow with older residents and kiosk operators, especially for shared-device privacy and plain-language error recovery.

**Evidence:** [INSERT VERIFIED FINAL EVALUATION SCORE AND DATE] — https://sevasetu-internship.duckdns.org/eval-dashboard  
**Live system:** https://sevasetu-internship.duckdns.org/  
**Scope:** Fictional/synthetic service; security and policy rules must not be relaxed for evaluation.
