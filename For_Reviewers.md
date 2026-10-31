### NOTE: I have provided all the required credentials in the `.env`(if needed for testing) file to allow reviewers to perform real-time testing.For MCP testing, I have used Gemini because I was unable to obtain a Claude API key. However, the code is designed to be compatible with any MCP-supported AI agent, including Claude, Gemini, and other supported models. You can configure and use whichever AI provider you prefer.

# SevaSetu — Independent Assessor Guide

## Project Overview

SevaSetu is a publicly deployed, OAuth-protected pension application system with two separate Model Context Protocol (MCP) servers:

- **Citizen MCP:** Allows authenticated citizens to check their application status, apply for pensions, and perform authorized citizen operations.
- **Officer MCP:** Allows authorized block officers to review applications, inspect cases, and approve or reject applications with recorded decisions.

The existing Flask portal and PostgreSQL database remain the system of record. Actions performed through AI assistants are reflected in the portal.

## AI Client Compatibility

The system implements MCP over Streamable HTTP and uses OAuth for authentication.

I implemented and tested the agent workflows using Gemini CLI because I did not have access to a Claude API key.

The MCP endpoints are designed to be usable by other compatible MCP clients, including Claude Code. The assessor may use their own compatible MCP client and AI model.

The server does not require the assessor to use my Gemini API key.

## 1. Production Endpoints

| Service | URL |
|---|---|
| SevaSetu Portal | https://sevasetu-internship.duckdns.org/ |
| Citizen MCP | https://sevasetu-internship.duckdns.org/mcp/citizen |
| Officer MCP | https://sevasetu-internship.duckdns.org/mcp/officer |
| Administrator Portal | https://sevasetu-internship.duckdns.org/admin |
| Synthetic OTP Login | https://sevasetu-internship.duckdns.org/reviewer/otp/login |
| Synthetic OTP Viewer | https://sevasetu-internship.duckdns.org/reviewer/otp |
| Evaluation Dashboard | https://sevasetu-internship.duckdns.org/eval-dashboard |

The Citizen and Officer MCP endpoints require OAuth authorization. An unauthenticated request may return HTTP 401.

## 2. Reviewer Credentials

The assessor administrator username and password are provided separately in the official Build for Bharat application form.

For security, production secrets such as PostgreSQL passwords, OAuth signing keys, access tokens, Gemini API keys, and SSH credentials are not included in this repository.

The application also supports a restricted synthetic OTP viewer. Its dedicated reviewer credentials, if needed, are supplied through a separate authorized channel.

The README and `.env.example` describe configuration without exposing production secrets.

## 3. Testing Citizen MCP

**Endpoint:** https://sevasetu-internship.duckdns.org/mcp/citizen

### Synthetic Test Identities

| Citizen | Mobile Number |
|---|---|
| Citizen A | 0000000001 |
| Citizen B | 0000000002 |
| Citizen C | 0000000008 |

### Authentication Steps

1. Open an OAuth-capable MCP client.
2. Connect to the Citizen MCP endpoint.
3. Start OAuth authorization.
4. Enter an authorized synthetic citizen mobile number.
5. Request an OTP.
6. Open the restricted synthetic OTP viewer in a separate browser session.
7. Authenticate to the OTP viewer using the configured reviewer access method.
8. Select the same synthetic mobile number.
9. Read the delivered OTP and enter it in the citizen authorization flow.
10. Approve the OAuth consent request.

Once authentication is successful, the client can invoke the citizen tools.

### Suggested Test

Ask the assistant:

"Please check the status of my pension application and tell me my application reference number."

Verify that the result belongs to the authenticated citizen.

For security testing, attempt to access an application owned by another citizen. The system should deny unauthorized access.

## 4. Testing Officer MCP

**Endpoint:** https://sevasetu-internship.duckdns.org/mcp/officer

### Authentication Steps

1. Connect an OAuth-capable MCP client to the Officer MCP endpoint.
2. Start OAuth authorization.
3. Sign in using the authorized assessor officer credentials.
4. Approve the OAuth consent request.
5. Use the available officer-specific tools.

### Suggested Tests

Ask:

"Show me the pension applications currently awaiting review in my authorized block."

Then:

"Show the details and current status of application [SYNTHETIC_APPLICATION_NUMBER]."

For a suitable pending synthetic application, request an approval or rejection with a recorded reason.

Verify the resulting application status and audit record in the portal.

Officer actions must comply with block-level authorization rules.

## 5. Evaluation Dashboard

Dashboard:

https://sevasetu-internship.duckdns.org/eval-dashboard

The evaluation system tests six scenarios:

| Case | Scenario |
|---|---|
| C01 | Citizen checks their own application |
| C02 | Unauthorized cross-citizen access is denied |
| C03 | Citizen withdraws an eligible application |
| O01 | Officer approves a pending application |
| O02 | Officer checks and rejects an application |
| C04 | Citizen submits a new pension application |

The dashboard contains real-agent evaluation reports, recorded outcomes, and database verification evidence.

The reports reflect the actual results of the corresponding evaluations. Earlier runs are retained to show improvements and debugging work.

## 6. Business Rules and Limitations

- Applicants must meet the configured age and block eligibility requirements.
- Citizen identity is verified through OTP and OAuth.
- Uploaded age-proof documents are linked through secure, one-time tickets.
- New applications are subject to the configured scheme deadline of October 31, 2026, at 11:59 PM IST.
- An application submitted after that deadline should be rejected under the existing business rules.
- Citizen and Officer MCP tools have separate authorization scopes.
- The synthetic OTP viewer supports only explicitly allowlisted demonstration mobile numbers.
- The system uses a simulated SMS gateway rather than a real telecom SMS provider.
- The portal and PostgreSQL database remain the authoritative record of all application decisions.

## 7. Running the Project Locally

For source-code review and self-hosted deployment:

1. Clone the private `sewasetu-assistant` repository.
2. Follow the installation instructions in `README.md`.
3. Copy `.env.example` to `.env`.
4. Configure the required local secrets and database settings.
5. Start the application using the documented Docker Compose commands.
6. Connect an OAuth-capable MCP client to the locally configured Citizen or Officer endpoint.

The repository does not contain live production secrets. A self-hosted installation requires its own environment configuration.

## 8. Security and Design Decisions

Three important architectural decisions guided the implementation:

**Separation of citizen and officer tools:** A citizen's AI assistant cannot access officer-specific operations.

**Portal as the system of record:** The agent performs authorized operations through the existing application and database logic, rather than maintaining a separate source of truth.

**Real-agent and database-verified evaluations:** The evaluation system measures not only conversational behavior, but also the actual database state after tool execution.

Further implementation details and design tradeoffs are documented in `DESIGN_NOTE.md`.

## 9. Assessor Notes

- The production URLs are intended for external MCP clients.
- Only synthetic demonstration identities should be used for testing.
- The evaluation dashboard can be reviewed without running the evaluator locally.
- Database-changing tests will alter application statuses and audit records.
