"""Limited, synthetic-only reviewer credentials; no administrator sessions.

The officer OAuth login and OTP helper deliberately use separate credentials.
No reviewer credential grants access to the Flask /admin routes.
"""

import os
import re
import secrets
import time


def _valid_username(username):
    return isinstance(username, str) and bool(re.fullmatch(r"[A-Za-z0-9_.@-]{1,64}", username))


def _credential_matches(username, password, configured_user, configured_password):
    """Require nonempty, non-default secrets and compare in constant time."""
    if not _valid_username(configured_user) or not isinstance(configured_password, str):
        return False
    if (len(configured_password) < 20 or configured_password.startswith("REPLACE_")
            or not isinstance(username, str) or not isinstance(password, str)):
        return False
    return secrets.compare_digest(username, configured_user) and secrets.compare_digest(password, configured_password)


def officer_subject(username, password, env=None):
    """Return a valid officer JWT subject, never an administrator Flask session."""
    env = os.environ if env is None else env
    admin_user = env.get("ADMIN_USERNAME", "admin")
    admin_password = env.get("ADMIN_PASSWORD", "")
    reviewer_user = env.get("OFFICER_REVIEWER_USERNAME", "")
    reviewer_password = env.get("OFFICER_REVIEWER_PASSWORD", "")
    # Reviewer username cannot shadow administrator credentials.
    if reviewer_user and reviewer_user == admin_user:
        return None
    if _credential_matches(username, password, reviewer_user, reviewer_password):
        return "officer:" + reviewer_user
    if (admin_password and isinstance(username, str) and isinstance(password, str)
            and secrets.compare_digest(username, admin_user)
            and secrets.compare_digest(password, admin_password)):
        return "officer:" + admin_user
    return None


def otp_reviewer_enabled(env=None):
    env = os.environ if env is None else env
    return (bool(_valid_username(env.get("REVIEWER_OTP_USERNAME", "")))
            and len(env.get("REVIEWER_OTP_PASSWORD", "")) >= 20
            and not env.get("REVIEWER_OTP_PASSWORD", "").startswith("REPLACE_")
            and bool(allowed_test_mobiles(env)))


def check_otp_reviewer(username, password, env=None):
    env = os.environ if env is None else env
    return otp_reviewer_enabled(env) and _credential_matches(
        username, password,
        env.get("REVIEWER_OTP_USERNAME", ""),
        env.get("REVIEWER_OTP_PASSWORD", ""),
    )


def allowed_test_mobiles(env=None):
    """Fail closed for malformed or non-synthetic phone numbers.

    Only 0000000001-0000000012 may be listed; this is intentionally NOT a
    general-purpose SMS inbox for actual citizens.
    """
    env = os.environ if env is None else env
    raw = env.get("REVIEWER_OTP_MOBILES", "")
    parts = [x.strip() for x in raw.split(",") if x.strip()]
    if not parts or len(parts) > 12 or len(parts) != len(set(parts)):
        return ()
    if any(not re.fullmatch(r"00000000(?:0[1-9]|1[0-2])", p) for p in parts):
        return ()
    return tuple(parts)


def delivered_otp(payload, mobile, now=None):
    """Extract one delivered OTP for a specifically allowed synthetic mobile.

    The simulated gateway has its own 1-4-second delivery latency. Do not
    expose undelivered SMS, other recipients, or non-OTP text.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("messages"), list):
        return None
    now = time.time() if now is None else now
    matches = []
    for entry in payload["messages"]:
        if not isinstance(entry, dict) or entry.get("to") != mobile or entry.get("delivered") is not True:
            continue
        sent_at = entry.get("sent_at")
        if not isinstance(sent_at, (int, float)) or not 0 <= now - sent_at <= 300:
            continue
        body = entry.get("text")
        if not isinstance(body, str):
            continue
        found = re.fullmatch(r"Your Sewa Setu OTP is ([0-9]{6})\. Valid for 5 minutes\.", body)
        if found:
            matches.append((sent_at, found.group(1)))
    return max(matches, key=lambda x: x[0])[1] if matches else None
