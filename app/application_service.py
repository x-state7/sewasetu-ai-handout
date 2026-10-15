"""Transaction-safe pension submission shared by the portal and future MCP tools.

This module intentionally does not import Flask. It accepts the existing portal's
validation and insertion functions so the browser and MCP apply identical rules.
"""

from contextlib import closing
from dataclasses import dataclass
import re
from typing import Callable, Literal, Mapping


SubmissionStatus = Literal["submitted", "existing", "invalid"]


@dataclass(frozen=True)
class SubmissionResult:
    status: SubmissionStatus
    application_id: int | None = None
    application_no: str | None = None
    application_status: str | None = None
    errors: tuple[str, ...] = ()


def submit_application(
    mobile: str,
    data: Mapping[str, str],
    doc_path: str,
    *,
    connect: Callable,
    validate: Callable,
    find_active: Callable,
    insert: Callable,
) -> SubmissionResult:
    """Validate and submit, or return the citizen's already-active application.

    The caller must derive mobile from an OTP-verified session or authenticated
    OAuth identity; it must NEVER take an unverified tool-supplied mobile value.

    Advisory locking serializes submissions per mobile, and the partial unique
    database index protects against other writers which bypass this function.
    Validation runs inside the lock, including the time-based scheme deadline.
    """
    if not isinstance(mobile, str) or not re.fullmatch(r"[0-9]{10}", mobile):
        raise ValueError("a verified 10-digit mobile identity is required")

    with closing(connect()) as conn:
        with conn:  # psycopg2 commits on success, rolls back on any exception
            with conn.cursor() as cur:
                # Lock the mobile BEFORE checking for an existing application.
                # PostgreSQL transaction advisory locks automatically release
                # on commit or rollback. hash collisions only cause contention.
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (mobile,),
                )

                errors, cleaned = validate(data, doc_path)
                if errors:
                    return SubmissionResult(status="invalid", errors=tuple(errors))

                current = find_active(cur, mobile)
                if current:
                    app_id, app_no, status = current
                    return SubmissionResult(
                        status="existing",
                        application_id=app_id,
                        application_no=app_no,
                        application_status=status,
                    )

                app_id, app_no = insert(cur, mobile, cleaned)
                return SubmissionResult(
                    status="submitted",
                    application_id=app_id,
                    application_no=app_no,
                    application_status="PENDING",
                )
