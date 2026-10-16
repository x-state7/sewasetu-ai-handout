#This adds a secure bridge between a verified uploaded document and an MCP application submission.
#A citizen who verifies their mobile number can upload age proof through the portal, receive a 
#temporary ticket and give that ticket to their AI 
#assistant. The database stores only a hash of the ticket.


"""One-use age-proof tickets for verified portal sessions and Citizen MCP."""

import hashlib
import os
import re
import secrets
from contextlib import closing
from pathlib import Path


def _hash(token):
    if not isinstance(token, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{24,96}", token
    ):
        return None
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def _valid_document(path, upload_root):
    if not isinstance(path, str) or not path or len(path) > 200:
        return False

    try:
        root = Path(upload_root).resolve(strict=True)
        target = Path(path)

        if target.is_symlink() or not target.is_file():
            return False

        return target.resolve(strict=True).is_relative_to(root)
    except (OSError, ValueError, RuntimeError):
        return False


def issue_ticket(connect, verified_mobile, path, upload_root):
    """Invoke only from an OTP-verified browser session."""

    if not re.fullmatch(r"\d{10}", verified_mobile or ""):
        raise ValueError("Verified mobile required")

    if not _valid_document(path, upload_root):
        raise ValueError("Valid uploaded document required")

    raw = secrets.token_urlsafe(32)

    with closing(connect()) as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mcp_document_claims
                    (token_hash, mobile, doc_path)
                    VALUES (%s, %s, %s)
                    """,
                    (_hash(raw), verified_mobile, path),
                )

    return raw


def resolve_ticket(cur, verified_mobile, raw, upload_root):
    """Resolve the ticket within the application transaction."""

    digest = _hash(raw)
    if digest is None:
        return None

    cur.execute(
        """
        SELECT doc_path
        FROM mcp_document_claims
        WHERE token_hash = %s
          AND mobile = %s
          AND used_at IS NULL
          AND created_at > NOW() - INTERVAL '30 minutes'
        FOR UPDATE
        """,
        (digest, verified_mobile),
    )

    row = cur.fetchone()

    if not row or not _valid_document(row[0], upload_root):
        return None

    return row[0]


def consume_ticket(cur, verified_mobile, raw, app_id):
    digest = _hash(raw)

    if digest is None:
        raise ValueError("Invalid ticket")

    cur.execute(
        """
        UPDATE mcp_document_claims
        SET used_at = NOW(),
            application_id = %s
        WHERE token_hash = %s
          AND mobile = %s
          AND used_at IS NULL
        """,
        (app_id, digest, verified_mobile),
    )

    if cur.rowcount != 1:
        raise ValueError("Ticket was already used")
