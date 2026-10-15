
"""Deployment-only MCP evaluation runner.

Usage from the app directory:
    python eval_runner.py

Requires deployed MCP endpoints and temporary test-persona
OAuth access tokens configured via environment variables.
"""

import asyncio
import json
import os
import uuid

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from eval_client import call_tool
from eval_scenarios import build_scenarios


REPORT_DIR = Path(
    os.getenv("EVAL_REPORT_DIR", "/var/sewasetu/eval-reports")
)

PERSONA_TOKEN_KEYS = {
    "citizen_a": "EVAL_CITIZEN_A_TOKEN",
    "citizen_b": "EVAL_CITIZEN_B_TOKEN",
    "officer": "EVAL_OFFICER_TOKEN",
}


def evaluate_response(case, response):
    """Check response structure and expected behavior."""

    kind = case.expectation

    if kind == "application_list":
        if not isinstance(response, list):
            return False, "Expected an application list"
        if not all(
            isinstance(row, dict)
            and "application_no" in row
            and "status" in row
            for row in response
        ):
            return False, "Invalid application list structure"
        return True, "List structure valid"

    if kind == "status_counts":
        if not isinstance(response, dict):
            return False, "Expected status-count object"
        if not all(
            isinstance(value, int)
            and not isinstance(value, bool)
            and value >= 0
            for value in response.values()
        ):
            return False, "Invalid status counts"
        return True, "Count structure valid"

    if kind == "pending_queue":
        if not isinstance(response, list):
            return False, "Expected pending queue"
        limit = case.arguments.get("limit", 25)
        if len(response) > limit:
            return False, "Queue exceeds limit"
        for row in response:
            if not isinstance(row, dict):
                return False, "Invalid queue row"
            if row.get("status") != "PENDING":
                return False, "Non-pending application in queue"
        return True, "Pending queue structure valid"

    if kind == "not_found":
        if response != {"found": False}:
            return False, "Ownership isolation check failed"
        return True, "Other citizen's application was not disclosed"

    if kind == "found":
        if not isinstance(response, dict):
            return False, "Expected application status object"
        if response.get("found") is not True:
            return False, "Expected application was not found"
        if response.get("application_no") != (
            case.arguments.get("application_no")
        ):
            return False, "Application reference mismatch"

        if (
            case.expected_status
            and response.get("status") != case.expected_status
        ):
            return False, "Unexpected application status"

        return True, "Expected application found"

    return False, "Unknown expectation type"


def check_configuration():
    citizen_url = os.environ["EVAL_CITIZEN_URL"]
    officer_url = os.environ["EVAL_OFFICER_URL"]

    if citizen_url.rstrip("/") == officer_url.rstrip("/"):
        raise RuntimeError(
            "Citizen and Officer endpoints must be separate"
        )

    tokens = {}
    for persona, key in PERSONA_TOKEN_KEYS.items():
        token = os.environ.get(key, "").strip()
        if not token:
            raise RuntimeError("Missing " + key)
        tokens[persona] = token

    if len(set(tokens.values())) != len(tokens):
        raise RuntimeError(
            "Each test persona must use a distinct OAuth token"
        )

    return {
        "citizen_a": (citizen_url, tokens["citizen_a"]),
        "citizen_b": (citizen_url, tokens["citizen_b"]),
        "officer": (officer_url, tokens["officer"]),
    }


async def execute_scenario(case, identities):
    url, token = identities[case.persona]

    try:
        response = await call_tool(
            url, token, case.tool, case.arguments
        )
        passed, reason = evaluate_response(case, response)
        status = "PASS" if passed else "FAIL"

    except Exception:
        # Exception details may contain URLs, response bodies or tokens.
        # Store only a generic error status in persisted reports.
        status = "ERROR"
        reason = "MCP connection, authentication or tool execution failed"

    return {
        "id": case.id,
        "persona": case.persona,
        "prompt": case.prompt,
        "tool": case.tool,
        "expectation": case.expectation,
        "status": status,
        "reason": reason,
    }


def save_report(report):
    REPORT_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)

    # Private directory: only the evaluation runner should write here.
    if REPORT_DIR.is_symlink():
        raise RuntimeError("Report directory must not be a symlink")

    path = REPORT_DIR / (report["run_id"] + ".json")
    data = json.dumps(report, indent=2, ensure_ascii=False)

    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(data)

    return path


async def run_evaluation():
    identities = check_configuration()
    scenarios = build_scenarios()

    if not scenarios:
        raise RuntimeError("No evaluation scenarios configured")

    outcomes = []
    for case in scenarios:
        result = await execute_scenario(case, identities)
        outcomes.append(result)
        print(case.id + ": " + result["status"])

    passed = sum(r["status"] == "PASS" for r in outcomes)
    failed = sum(r["status"] == "FAIL" for r in outcomes)
    errors = sum(r["status"] == "ERROR" for r in outcomes)
    total = len(outcomes)

    report = {
        "run_id": "eval-" + uuid.uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "pass_rate": round(
                100 * passed / total, 2
            ) if total else 0,
        },
        "results": outcomes,
    }

    path = save_report(report)

    print("Evaluation results saved.")
    print("Total:", total)
    print("Passed:", passed)
    print("Failed:", failed)
    print("Errors:", errors)
    print("Pass rate:", report["summary"]["pass_rate"])
    print("Report path:", path)

    return report


if __name__ == "__main__":
    asyncio.run(run_evaluation())
