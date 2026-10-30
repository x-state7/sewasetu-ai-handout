#!/usr/bin/env python3
"""Idempotently add reviewer-only credentials to an EXISTING private .env.

Does not display, log or overwrite existing values. Never run on a publicly
shared environment file. Run on the EC2 host before recreating ONLY app service.
"""

import os
import secrets
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"

if not ENV.is_file() or ENV.is_symlink():
    sys.exit("Missing regular .env file; use generate_aws_env.py on NEW deployments")

original = ENV.read_text(encoding="utf-8")
existing = {line.split("=", 1)[0].strip() for line in original.splitlines()
            if "=" in line and not line.lstrip().startswith("#")}
additions = {
    "OFFICER_REVIEWER_USERNAME": "reviewer-officer",
    "OFFICER_REVIEWER_PASSWORD": secrets.token_urlsafe(32),
    "REVIEWER_OTP_USERNAME": "reviewer-otp",
    "REVIEWER_OTP_PASSWORD": secrets.token_urlsafe(32),
    "REVIEWER_OTP_MOBILES": "0000000001,0000000002,0000000008",
}
missing = {key: value for key, value in additions.items() if key not in existing}
if not missing:
    print("Reviewer settings already exist; left .env unchanged (check their strength manually).")
    sys.exit(0)

new_contents = original.rstrip("\n") + "\n\n# Synthetic reviewer access (never share in Git)\n" + "".join(
    f"{name}={value}\n" for name, value in missing.items()
)
fd, tmp = tempfile.mkstemp(prefix=".sewasetu-env-", dir=str(ROOT), text=True)
try:
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(new_contents)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, ENV)
except BaseException:
    try:
        os.unlink(tmp)
    except OSError:
        pass
    raise
os.chmod(ENV, 0o600)
print("Added missing reviewer configuration names:", ", ".join(missing))
print("Private passwords were generated but not displayed. Share only with authorized reviewers.")
