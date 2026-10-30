#!/usr/bin/env python3
"""Create a unique private AWS .env; never overwrites an existing one."""
import os
import re
import secrets
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
if len(sys.argv) != 2:
    sys.exit("Usage: python3 deploy/generate_aws_env.py SUBDOMAIN.duckdns.org")
domain = sys.argv[1].strip().lower()
if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+", domain):
    sys.exit("Expected a valid DNS hostname without https://")
path = root / ".env"
if path.exists():
    sys.exit(".env already exists; refusing to overwrite existing credentials")
values = {
    "SECRET_KEY": secrets.token_hex(32),
    "DB_PASSWORD": secrets.token_hex(24),
    "ADMIN_USERNAME": "admin",
    "ADMIN_PASSWORD": secrets.token_urlsafe(32),
    "OFFICER_REVIEWER_USERNAME": "reviewer-officer",
    "OFFICER_REVIEWER_PASSWORD": secrets.token_urlsafe(32),
    "REVIEWER_OTP_USERNAME": "reviewer-otp",
    "REVIEWER_OTP_PASSWORD": secrets.token_urlsafe(32),
    "REVIEWER_OTP_MOBILES": "0000000001,0000000002,0000000008",
    "PUBLIC_HOSTNAME": domain,
    "PUBLIC_BASE_URL": "https://" + domain,
    "MCP_JWKS_URL": "https://" + domain + "/.well-known/jwks.json",
    "EVAL_DASHBOARD_USERNAME": "evaluator",
    "EVAL_DASHBOARD_PASSWORD": secrets.token_urlsafe(32),
    "EVAL_CITIZEN_URL": "https://" + domain + "/mcp/citizen",
    "EVAL_OFFICER_URL": "https://" + domain + "/mcp/officer",
    "SEVASETU_SEED_FILE": "./seed/demo-seed.sql",
}
original = (root / ".env.example").read_text(encoding="utf-8").splitlines()
output = []
replaced = set()
for line in original:
    name = line.split("=", 1)[0].strip()
    if name in values and not line.lstrip().startswith("#"):
        output.append(f"{name}={values[name]}")
        replaced.add(name)
    else:
        output.append(line)
for name in values.keys() - replaced:
    output.append(f"{name}={values[name]}")
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    handle.write("\n".join(output) + "\n")
print("Created a new private .env in the project root (chmod 600).")
print("Passwords were generated but not displayed. Edit using: nano .env")
