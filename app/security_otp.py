"""Shared, one-time OTP issuance/verification for portal and OAuth.

Requires the otp_verify_attempts table installed by migration 002.
Limits are keyed by mobile, held behind a PostgreSQL advisory transaction lock,
so they apply across workers/processes rather than per in-memory Flask session.
"""

import secrets
from contextlib import closing
from datetime import datetime, timedelta

ISSUE_WINDOW = timedelta(hours=1)
ISSUE_COOLDOWN = timedelta(seconds=60)
MAX_ISSUES = 3
VERIFY_WINDOW = timedelta(minutes=15)
MAX_VERIFY_ATTEMPTS = 5


def _lock(cursor, mobile):
    cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 412))", ("otp:" + mobile,))


def issue_otp(connect, mobile, deliver):
    """Issue code to SMS; return False when rate-limited. Raises if DB/SMS fails."""
    if not mobile.isascii() or not mobile.isdigit() or len(mobile) != 10:
        return False
    now = datetime.now()
    with closing(connect()) as conn:
        with conn:
            with conn.cursor() as cur:
                _lock(cur, mobile)
                cur.execute("SELECT count(*), max(attempted_at) FROM otp_send_attempts "
                            "WHERE mobile = %s AND attempted_at >= %s",
                            (mobile, now - ISSUE_WINDOW))
                count, latest = cur.fetchone()
                if count >= MAX_ISSUES or (latest and now - latest < ISSUE_COOLDOWN):
                    return False
                code = "%06d" % secrets.randbelow(1_000_000)
                cur.execute("INSERT INTO otp_send_attempts (mobile, attempted_at) VALUES (%s, %s)",
                            (mobile, now))
                cur.execute("INSERT INTO otps (mobile, code, created_at) VALUES (%s, %s, %s)",
                            (mobile, code, now))
    # Deliver only after commit so the OTP exists when the recipient receives it.
    deliver(mobile, "Your Sewa Setu OTP is %s. Valid for 5 minutes." % code)
    return True


def verify_otp(connect, mobile, supplied, validity_seconds):
    """Consume the latest OTP once; count failed attempts across all sessions."""
    if (not mobile or not mobile.isascii() or not mobile.isdigit() or len(mobile) != 10
            or not isinstance(supplied, str) or len(supplied) != 6
            or not supplied.isascii() or not supplied.isdigit()):
        return False
    now = datetime.now()
    with closing(connect()) as conn:
        with conn:
            with conn.cursor() as cur:
                _lock(cur, mobile)
                cur.execute("SELECT count(*) FROM otp_verify_attempts "
                            "WHERE mobile = %s AND attempted_at >= %s",
                            (mobile, now - VERIFY_WINDOW))
                if cur.fetchone()[0] >= MAX_VERIFY_ATTEMPTS:
                    return False
                cur.execute("SELECT code, created_at FROM otps "
                            "WHERE mobile = %s ORDER BY id DESC LIMIT 1", (mobile,))
                row = cur.fetchone()
                valid = (bool(row) and now - row[1] <= timedelta(seconds=validity_seconds)
                         and now >= row[1] and secrets.compare_digest(row[0], supplied))
                if valid:
                    # Invalidate every outstanding code for the same phone on success.
                    cur.execute("DELETE FROM otps WHERE mobile = %s", (mobile,))
                    cur.execute("DELETE FROM otp_verify_attempts WHERE mobile = %s", (mobile,))
                    return True
                cur.execute("INSERT INTO otp_verify_attempts (mobile, attempted_at) VALUES (%s, %s)",
                            (mobile, now))
                return False
