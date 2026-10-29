
"""Predeployment configuration checks. No database writes."""

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit


ERRORS = []


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        ERRORS.append(f"Missing configuration: {name}")
    return value


def check_https(name, value):
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        valid = False

    if not valid:
        ERRORS.append(f"{name} must be a valid HTTPS origin or URL")


def main():
    base = required("PUBLIC_BASE_URL")
    hostname = required("PUBLIC_HOSTNAME")
    secret = required("SECRET_KEY")
    db_password = required("DB_PASSWORD")
    if db_password and "REPLACE_" in db_password.upper():
        ERRORS.append("DB_PASSWORD is still a placeholder")
    required("ADMIN_USERNAME")
    admin_password = required("ADMIN_PASSWORD")
    jwks = required("MCP_JWKS_URL")
    dashboard_password = required("EVAL_DASHBOARD_PASSWORD")
    required("EVAL_DASHBOARD_USERNAME")

    if base:
        check_https("PUBLIC_BASE_URL", base)

    if jwks:
        check_https("MCP_JWKS_URL", jwks)

    if base and hostname:
        try:
            if urlsplit(base).hostname != hostname:
                ERRORS.append(
                    "PUBLIC_HOSTNAME does not match PUBLIC_BASE_URL"
                )
        except ValueError:
            ERRORS.append("Invalid public hostname")

    if secret and (len(secret.encode("utf-8")) < 32 or "REPLACE_" in secret.upper()):
        ERRORS.append("SECRET_KEY must be a randomly generated value of at least 32 bytes")

    if admin_password and (
        "REPLACE_" in admin_password.upper()
        or len(admin_password) < 16
        or admin_password == "change-me-before-deploying"
    ):
        ERRORS.append("Use a strong non-default admin password")

    if dashboard_password and (len(dashboard_password) < 24 or "REPLACE_" in dashboard_password.upper()):
        ERRORS.append("Evaluation dashboard password is too short")

    required_files = [
        "app/app.py",
        "app/oauth.py",
        "app/mcp_auth.py",
        "app/mcp_citizen.py",
        "app/mcp_officer.py",
        "app/eval_runner.py",
        "app/eval_dashboard.py",
        "app/migrations/001_submission_constraints.sql",
        "app/migrations/002_otp_security.sql",
        "app/migrations/003_mcp_document_claims.sql",
        "seed/demo-seed.sql",
        "deploy/Caddyfile",
    ]

    root = Path(__file__).resolve().parent.parent

    for filename in required_files:
        if not (root / filename).is_file():
            ERRORS.append("Missing file: " + filename)

    if ERRORS:
        print("PREFLIGHT FAILED")
        for problem in ERRORS:
            print("-", problem)
        return 1

    print("Static configuration preflight passed.")
    print("Runtime, OAuth, database and network checks still required.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
