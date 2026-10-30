#!/usr/bin/env python3
"""Read-only local checks for SevaSetu submission; no Docker/network calls."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASS = 0
WARN = 0


def report(success, message, warning=False):
    global PASS, WARN
    if success:
        PASS += 1
        print("PASS", message)
    else:
        WARN += 1
        print("WARN", message)


def git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)
    return p.returncode, p.stdout.strip()


required = ["app/oauth.py", "app/reviewer_access.py", "app/templates/reviewer_otp.html",
            "app/eval_agent.py", "app/eval_public.py", "app/evaluation/cases.example.json",
            "seed/eval-seed.sql", "docker-compose.yml", "deploy/Caddyfile"]
for name in required:
    report((ROOT / name).is_file(), f"Required source: {name}")

if (ROOT / ".env").is_file():
    values = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    for name in ("OFFICER_REVIEWER_PASSWORD", "REVIEWER_OTP_PASSWORD"):
        report(len(values.get(name, "")) >= 20 and "REPLACE" not in values.get(name, ""),
               "Private reviewer credential is configured: " + name)
    report(values.get("OFFICER_REVIEWER_USERNAME") not in (None, "", values.get("ADMIN_USERNAME", "admin")),
           "Reviewer officer identity differs from admin")
    report(bool(values.get("REVIEWER_OTP_MOBILES")), "Synthetic mobile whitelist configured")
else:
    report(False, "Private .env not present (expected in a deployed clone)")

status, tracked_env = git("ls-files", "--error-unmatch", ".env")
report(status != 0, ".env is not tracked in Git")
status, branch = git("rev-parse", "--is-inside-work-tree")
report(status == 0 and branch == "true", "Git repository/history exists")
status, dirty = git("status", "--porcelain")
report(status == 0 and not dirty, "Source working tree is committed / clean")
status, remote = git("remote", "-v")
report(status == 0 and "sewasetu-assistant" in remote,
       "Remote names the requested sewasetu-assistant repository")

# A source dataset may have been provided in the starter repo. Do not automatically
# rewrite history, but require manual permission and sensitivity review.
status, _ = git("ls-files", "--error-unmatch", "seed/seed.sql")
report(status != 0, "Original 100k-row data export is not committed (or manual review complete)")

report((ROOT / "private-eval/evidence/read-only-3of3.json").is_file(),
       "Local copy of the original real 3/3 report exists")

print(f"\n{PASS} passed, {WARN} warnings. Warnings require human review before submission.")
# Nonzero status useful in CI; warns also include intentionally manual items.
sys.exit(1 if WARN else 0)
