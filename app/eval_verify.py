
"""Verify real MCP conversation outcomes against PostgreSQL."""

import json
import os
import re
import sys
import uuid

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import psycopg2


def verify(conn, case):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, mobile, status, doc_path
            FROM applications
            WHERE application_no = %s
            """,
            (case["application_no"],),
        )

        rows = cur.fetchall()

        if case.get("expect_absent"):
            return (
                len(rows) == 0,
                "Application absent"
                if not rows
                else "Unexpected application found",
            )

        if len(rows) != 1:
            return (
                False,
                "Expected one application, found " + str(len(rows)),
            )

        app_id, mobile, status, doc = rows[0]

        checks = [
            (
                mobile == case["test_mobile"],
                "Owner mismatch",
            ),
            (
                status == case["expected_status"],
                "Status mismatch",
            ),
        ]

        if case.get("require_age_proof"):
            checks.append((
                bool(doc),
                "Missing age proof reference",
            ))

        if case.get("expected_audit_action"):
            cur.execute(
                """
                SELECT COUNT(*)
                FROM audit_log
                WHERE application_id = %s
                  AND action = %s
                """,
                (
                    app_id,
                    case["expected_audit_action"],
                ),
            )

            checks.append((
                cur.fetchone()[0] > 0,
                "Missing audit action",
            ))

        if "expected_active_count" in case:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM applications
                WHERE mobile = %s
                  AND status IN (
                      'PENDING',
                      'APPROVED',
                      'DEEMED_APPROVED'
                  )
                """,
                (mobile,),
            )

            checks.append((
                cur.fetchone()[0]
                == case["expected_active_count"],
                "Active application count mismatch",
            ))

        failures = [
            reason
            for passed, reason in checks
            if not passed
        ]

        return (
            not failures,
            "; ".join(failures)
            or "Database assertions passed",
        )


def main():
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python eval_verify.py "
            "/cases/private_cases.json"
        )

    cases = json.loads(
        Path(sys.argv[1]).read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(cases, list) or not cases:
        raise ValueError(
            "Nonempty test case list required"
        )

    outcomes = []

    with closing(
        psycopg2.connect(
            host=os.getenv("DB_HOST", "db"),
            dbname=os.getenv("DB_NAME", "sewasetu"),
            user=os.getenv("DB_USER", "sewasetu"),
            password=os.environ["DB_PASSWORD"],
        )
    ) as conn:

        for case in cases:
            if not re.fullmatch(
                r"[A-Za-z0-9-]{3,40}",
                case.get("application_no", ""),
            ):
                raise ValueError(
                    "Invalid test application reference"
                )

            if not re.fullmatch(
                r"\d{10}",
                case.get("test_mobile", ""),
            ):
                raise ValueError(
                    "Invalid test mobile"
                )

            passed, reason = verify(conn, case)

            # Only synthetic, reviewed public fields.
            outcomes.append({
                "id": case["id"],
                "persona": case["persona_public"],
                "prompt": case["goal_public"],
                "conversation": case.get(
                    "conversation_public", []
                )[:30],
                "tool": (
                    "MCP conversation + PostgreSQL"
                ),
                "status": (
                    "PASS" if passed else "FAIL"
                ),
                "reason": reason,
            })

    passed = sum(
        result["status"] == "PASS"
        for result in outcomes
    )

    report = {
        "run_id": "eval-" + uuid.uuid4().hex,
        "created_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "summary": {
            "total": len(outcomes),
            "passed": passed,
            "failed": len(outcomes) - passed,
            "errors": 0,
            "pass_rate": round(
                passed * 100 / len(outcomes),
                2,
            ),
        },
        "results": outcomes,
    }

    output_dir = Path(
        os.environ.get(
            "EVAL_PUBLIC_REPORT_DIR",
            "/var/sewasetu/eval-public",
        )
    )

    output_dir.mkdir(
        mode=0o700,
        parents=True,
        exist_ok=True,
    )

    target = output_dir / (
        report["run_id"] + ".json"
    )

    descriptor = os.open(
        target,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        0o600,
    )

    with os.fdopen(
        descriptor,
        "w",
        encoding="utf-8",
    ) as output:
        json.dump(
            report,
            output,
            ensure_ascii=False,
            indent=2,
        )

    print(json.dumps(report["summary"]))

    return (
        0
        if passed == len(outcomes)
        else 1
    )


if __name__ == "__main__":
    sys.exit(main())
