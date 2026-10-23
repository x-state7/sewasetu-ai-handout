# this will Reuse our existing validate_application(), 
# active_application() and create_application() functions.
#Submit pension applications using the verified citizen's mobile number.
#Withdraw only the authenticated citizen's pending application.
#Restrict officer queries and decisions to explicitly configured blocks.
#Reuse the original audit_log table.
#- Use conditional database updates to avoid conflicting decisions.


"""Shared, transactional citizen/officer MCP actions.

The Flask portal remains the system of record.
Caller identities must come from verified OAuth tokens.
"""

import os
import re
from contextlib import closing

import app as portal

from application_service import submit_application as atomic_submit
from mcp_document_claims import resolve_ticket, consume_ticket


def scheme_requirements():
    return {
        "minimum_age": portal.MIN_AGE,
        "eligible_blocks": portal.BLOCKS,
        "deadline": portal.SCHEME_DEADLINE.isoformat(),
        "applications_open": (
            portal.deadline_remaining() is not None
        ),
        "dob_format": "DD/MM/YYYY",
        "age_proof": (
            "Upload JPG, PNG or PDF (up to 5 MB) "
            "using the OTP-verified portal."
        ),
        "verify_mobile_url": (
            os.environ["PUBLIC_BASE_URL"].rstrip("/") + "/apply"
        ),
        "document_upload_url": (
            os.environ["PUBLIC_BASE_URL"].rstrip("/")
            + "/mcp/age-proof"
        ),
        "required_fields": [
            "applicant_name",
            "dob",
            "village",
            "block",
            "bank_account",
            "ifsc",
            "document_ticket",
        ],
    }


def submit_as_citizen(
    mobile, details, document_ticket, confirmed
):
    if confirmed is not True:
        return {"status": "confirmation_required"}

    if not document_ticket:
        return {"status": "document_ticket_required"}

    result = atomic_submit(
        mobile,
        details,
        "",
        connect=portal.get_db,
        validate=portal.validate_application,
        find_active=portal.active_application,
        insert=portal.create_application,
        document_ticket=document_ticket,
        resolve_document=(
            lambda cur, owner, ticket: resolve_ticket(
                cur, owner, ticket, portal.UPLOAD_DIR
            )
        ),
        consume_document=consume_ticket,
    )

    return {
        "status": result.status,
        "application_no": result.application_no,
        "application_status": result.application_status,
        "errors": list(result.errors),
    }


def withdraw_as_citizen(
    mobile, application_no, confirmed
):
    if confirmed is not True:
        return {"status": "confirmation_required"}

    if not isinstance(application_no, str) or not re.fullmatch(
        r"[A-Za-z0-9-]{3,40}", application_no
    ):
        return {"status": "invalid_reference"}

    with closing(portal.get_db()) as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE applications
                    SET status = 'WITHDRAWN',
                        decided_at = %s,
                        decided_by = 'APPLICANT'
                    WHERE mobile = %s
                      AND application_no = %s
                      AND status = 'PENDING'
                    RETURNING id
                    """,
                    (
                        portal.now_ist(),
                        mobile,
                        application_no,
                    ),
                )

                row = cur.fetchone()

                if row:
                    portal.write_audit(
                        cur,
                        row[0],
                        "WITHDRAW",
                        "applicant:" + mobile,
                    )
                    return {
                        "status": "withdrawn",
                        "application_no": application_no,
                    }

                return {
                    "status": "not_found_or_not_pending"
                }


def _blocks():
    """Explicit block permissions for the departmental login."""

    text = os.environ.get(
        "OFFICER_ALLOWED_BLOCKS", ""
    )

    requested = [
        value.strip()
        for value in text.split(",")
        if value.strip()
    ]

    if not requested or any(
        value not in portal.BLOCKS
        for value in requested
    ):
        raise PermissionError(
            "Officer block permissions are not configured"
        )

    return list(dict.fromkeys(requested))


def officer_queue(limit=20):
    allowed = _blocks()

    if type(limit) is not int:
        raise ValueError("Limit must be an integer")

    limit = min(50, max(1, limit))

    with closing(portal.get_db()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    application_no,
                    applicant_name,
                    block,
                    submitted_at
                FROM applications
                WHERE status = 'PENDING'
                  AND block = ANY(%s)
                ORDER BY submitted_at ASC, id ASC
                LIMIT %s
                """,
                (allowed, limit),
            )

            return [
                {
                    "application_no": reference,
                    "status": "PENDING",
                    "applicant_name": name,
                    "block": block,
                    "submitted_at": (
                        submitted.isoformat()
                        if submitted else None
                    ),
                }
                for reference, name, block, submitted
                in cur.fetchall()
            ]


def officer_detail(application_no):
    allowed = _blocks()

    with closing(portal.get_db()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    application_no,
                    applicant_name,
                    dob,
                    village,
                    block,
                    status,
                    submitted_at,
                    doc_path
                FROM applications
                WHERE application_no = %s
                  AND block = ANY(%s)
                LIMIT 1
                """,
                (application_no, allowed),
            )

            row = cur.fetchone()

            if not row:
                return {"found": False}

            (
                app_id,
                reference,
                name,
                dob,
                village,
                block,
                status,
                submitted_at,
                doc_path,
            ) = row

            cur.execute(
                """
                SELECT action, note, at
                FROM audit_log
                WHERE application_id = %s
                ORDER BY at DESC
                LIMIT 20
                """,
                (app_id,),
            )

            audit = [
                {
                    "action": action,
                    "note": note,
                    "at": (
                        at.isoformat()
                        if at else None
                    ),
                }
                for action, note, at
                in cur.fetchall()
            ]

            return {
                "found": True,
                "application_no": reference,
                "applicant_name": name,
                "dob": dob.isoformat() if dob else None,
                "village": village,
                "block": block,
                "status": status,
                "submitted_at": (
                    submitted_at.isoformat()
                    if submitted_at else None
                ),
                "age_proof_uploaded": bool(doc_path),
                "audit": audit,
            }


def officer_decide(
    application_no,
    new_status,
    officer,
    reason,
    confirmed,
):
    if confirmed is not True:
        return {"status": "confirmation_required"}

    if new_status not in ("APPROVED", "REJECTED"):
        raise ValueError("Invalid status")

    if not isinstance(reason, str) or len(reason) > 500:
        return {"status": "invalid_reason"}

    if (
        new_status == "REJECTED"
        and len(reason.strip()) < 10
    ):
        return {"status": "reason_required"}

    if not isinstance(application_no, str) or not re.fullmatch(
        r"[A-Za-z0-9-]{3,40}", application_no
    ):
        return {"status": "invalid_reference"}

    allowed = _blocks()

    with closing(portal.get_db()) as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE applications
                    SET status = %s,
                        decided_at = %s,
                        decided_by = %s
                    WHERE application_no = %s
                      AND block = ANY(%s)
                      AND status = 'PENDING'
                    RETURNING id
                    """,
                    (
                        new_status,
                        portal.now_ist(),
                        officer,
                        application_no,
                        allowed,
                    ),
                )

                row = cur.fetchone()

                if not row:
                    return {
                        "status":
                            "not_found_or_not_pending_or_unassigned"
                    }

                portal.write_audit(
                    cur,
                    row[0],
                    new_status,
                    "admin:" + officer,
                    reason.strip(),
                )

                return {
                    "status": "decided",
                    "application_no": application_no,
                    "application_status": new_status,
                }
