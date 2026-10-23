"""Live, real-client MCP + OpenAI-compatible assistant + PostgreSQL evaluation.

This runner NEVER synthesizes passing reports. It requires an LLM, authenticated
Streamable HTTP MCP servers, and access to the real deployment database.
Use only disposable/authorized synthetic identities. Writes are explicitly gated.

From app/: python eval_agent.py /app/evaluation/cases.private.json
"""

import asyncio
import json
import os
import re
import sys
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx2
import psycopg2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from eval_client import normalize_result, validate_url
from eval_verify import verify

TOKENS = {
    "citizen_a": "EVAL_CITIZEN_A_TOKEN",
    "citizen_b": "EVAL_CITIZEN_B_TOKEN",
    "officer": "EVAL_OFFICER_TOKEN",
}
WRITE_TOOLS = {
    "submit_pension_application", "withdraw_my_application",
    "approve_application", "reject_application",
}
WRITE_CONFIRMATION = "YES_I_AUTHORIZE_SYNTHETIC_TEST_WRITES"
MAX_CASES = 30
MAX_TURNS = 12


def validate_llm_url(raw):
    parsed = urlsplit(raw)
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Invalid EVAL_LLM_BASE_URL")
    if parsed.scheme == "https":
        return raw.rstrip("/")
    # Docker DNS names are allowed only with explicit operator permission.
    if parsed.scheme == "http" and (
        parsed.hostname in ("localhost", "127.0.0.1")
        or os.getenv("EVAL_ALLOW_INTERNAL_LLM_HTTP") == "YES"
    ):
        return raw.rstrip("/")
    raise ValueError("Use HTTPS for LLM, or authorize an internal test service")


def configuration():
    citizen_url = validate_url(os.environ["EVAL_CITIZEN_URL"])
    officer_url = validate_url(os.environ["EVAL_OFFICER_URL"])
    if citizen_url.rstrip("/") == officer_url.rstrip("/"):
        raise ValueError("MCP role endpoints must be distinct")
    tokens = {key: os.environ.get(env, "").strip() for key, env in TOKENS.items()}
    if not all(tokens.values()) or len(set(tokens.values())) != len(tokens):
        raise ValueError("Issue distinct real OAuth bearer tokens for three test identities")
    llm_url = validate_llm_url(os.environ["EVAL_LLM_BASE_URL"])
    model = os.environ["EVAL_LLM_MODEL"].strip()
    if not model:
        raise ValueError("EVAL_LLM_MODEL is required")
    return {
        "citizen": citizen_url, "officer": officer_url,
        "tokens": tokens, "llm": llm_url, "model": model,
        "api_key": os.getenv("EVAL_LLM_API_KEY", ""),
        "allow_writes": os.getenv("EVAL_ENABLE_WRITES", "") == WRITE_CONFIRMATION,
    }


def load_cases(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 120_000:
        raise ValueError("Use a regular private JSON cases file under 120 KB")
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not (1 <= len(cases) <= MAX_CASES):
        raise ValueError("Require 1–30 test cases")
    seen = set()
    for case in cases:
        if not isinstance(case, dict) or not re.fullmatch(r"[A-Z0-9_-]{2,24}", case.get("id", "")):
            raise ValueError("Each case needs a short uppercase ID")
        if case["id"] in seen:
            raise ValueError("Duplicate test case ID")
        seen.add(case["id"])
        if case.get("identity") not in TOKENS:
            raise ValueError("Unknown test identity")
        if case.get("role") not in ("citizen", "officer"):
            raise ValueError("Unknown role")
        if (case["role"] == "officer") != (case["identity"] == "officer"):
            raise ValueError("Persona identity/role mismatch")
        if not isinstance(case.get("persona"), dict):
            raise ValueError("Persona needs fictional name, age, village, style and goal")
        if any(not case["persona"].get(k) for k in ("name", "age", "village", "speaking_style", "goal")):
            raise ValueError("Persona fields missing")
        steps = case.get("user_turns")
        if not isinstance(steps, list) or not steps or len(steps) > 5 or not all(isinstance(t, str) and t.strip() and len(t) <= 1800 for t in steps):
            raise ValueError("Each case needs 1–5 scripted citizen/officer turns")
        if not isinstance(case.get("required_tools"), list) or not case["required_tools"]:
            raise ValueError("Every case must assert which tools ran")
        if not isinstance(case.get("db_expectation"), dict):
            raise ValueError("Every case must specify a database expectation")
        db = case["db_expectation"]
        if not re.fullmatch(r"\d{10}", db.get("test_mobile", "")):
            raise ValueError("Database mobile must be a synthetic 10 digit test mobile")
        if db.get("application_no") is not None and not re.fullmatch(r"[A-Za-z0-9-]{3,40}", db["application_no"]):
            raise ValueError("Invalid application reference")
        if not db.get("expected_status") and not db.get("expect_absent"):
            raise ValueError("Expected status or absence must be explicit")
        if case.get("mutation") not in (True, False):
            raise ValueError("Specify mutation true/false explicitly")
        if case["mutation"] and not any(t in WRITE_TOOLS for t in case["required_tools"]):
            raise ValueError("Mutation scenario must require the write tool")
        if not case["mutation"] and any(t in WRITE_TOOLS for t in case["required_tools"]):
            raise ValueError("Read-only scenario requires read-only tools")
    return cases


def redacted(text, secrets=()):
    """Public report fields only; secrets are never published as tool arguments/results."""
    content = str(text)
    for item in sorted({str(x) for x in secrets if x and len(str(x)) >= 4}, key=len, reverse=True):
        content = content.replace(item, "[REDACTED]")
    content = re.sub(r"(?i)bearer\s+\S+", "Bearer [REDACTED]", content)
    content = re.sub(r"\b\d{9,18}\b", "[REDACTED_NUMBER]", content)
    content = re.sub(r"\b[A-Z]{4}0[A-Z0-9]{6}\b", "[REDACTED_IFSC]", content)
    content = re.sub(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{24,96}(?![A-Za-z0-9_-])", "[REDACTED_TOKEN]", content)
    return content[:1400]


def require_disposable_fixture(conn):
    """Fail closed before write-enabled runs on non-demo/large databases."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM applications")
        count = cur.fetchone()[0]
        if count < 3 or count > 200:
            raise RuntimeError("Refusing writes: not a small isolated demo database")
        cur.execute("""SELECT application_no, mobile, status FROM applications
                       WHERE application_no IN ('DEMO000001', 'DEMO000002', 'DEMO000008')""")
        rows = {ref: (mobile, status) for ref, mobile, status in cur.fetchall()}
    expected = {
        "DEMO000001": ("0000000001", "PENDING"),
        "DEMO000002": ("0000000002", "PENDING"),
        "DEMO000008": ("0000000008", "PENDING"),
    }
    if rows != expected:
        raise RuntimeError("Refusing writes: demo fixtures are missing or already modified")


def snapshot(conn, db):
    """Capture before/after state; no test mutation may pass on pre-existing data."""
    ref = db.get("application_no")
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*), COALESCE(MAX(id), 0) FROM applications WHERE mobile = %s", (db["test_mobile"],))
        total, newest_id = cur.fetchone()
        status, audit_counts = None, {}
        if ref:
            cur.execute("SELECT id, status FROM applications WHERE application_no = %s", (ref,))
            row = cur.fetchone()
            if row:
                app_id, status = row
                cur.execute("SELECT action, COUNT(*) FROM audit_log WHERE application_id = %s GROUP BY action", (app_id,))
                audit_counts = dict(cur.fetchall())
    return {"total": total, "newest_id": newest_id, "status": status, "audit": audit_counts}


def check_db_after(conn, expectation, before, tool_calls, mutation):
    data = dict(expectation)
    if not data.get("application_no"):
        # Only a successful submission can produce a new reference; never trust LLM text.
        submitted = [result for name, result in tool_calls if name == "submit_pension_application" and isinstance(result, dict) and result.get("status") == "submitted"]
        if not submitted:
            return False, "No successfully submitted application reference from MCP"
        data["application_no"] = submitted[-1].get("application_no")
    if not isinstance(data.get("application_no"), str) or not re.fullmatch(r"[A-Za-z0-9-]{3,40}", data["application_no"]):
        return False, "Invalid application reference in MCP result"
    passed, reason = verify(conn, data)
    if not passed:
        return False, reason
    after = snapshot(conn, data)
    if mutation:
        if not (after["total"] > before["total"] or after["status"] != before["status"]):
            return False, "No new persisted database mutation in this evaluation"
        if after["total"] > before["total"] and after["newest_id"] <= before["newest_id"]:
            return False, "A new application row could not be established"
        audit_action = data.get("expected_audit_action")
        if audit_action and after["audit"].get(audit_action, 0) <= before["audit"].get(audit_action, 0) and after["status"] != before["status"]:
            return False, "No new audit action recorded during the evaluation"
    elif after != before:
        return False, "Read-only conversation changed the test database state"
    return True, "Verified against PostgreSQL after real MCP conversation"


def assert_tool_behavior(case, calls):
    names = [name for name, _ in calls]
    if not all(name in names for name in case["required_tools"]):
        return False, "Required MCP tools were not invoked"
    for tool in case["required_tools"]:
        if not any(name == tool and not (isinstance(result, dict) and "error" in result)
                   for name, result in calls):
            return False, "Required MCP tool returned only errors: " + tool
    for expectation in case.get("tool_assertions", []):
        tool = expectation["tool"]
        matches = [result for name, result in calls if name == tool]
        if "contains_application_no" in expectation:
            target = expectation["contains_application_no"]
            if not any(isinstance(result, list) and any(
                isinstance(row, dict) and row.get("application_no") == target
                for row in result) for result in matches):
                return False, "Application not present in MCP list response"
        else:
            field, value = expectation["field"], expectation["equals"]
            if not any(isinstance(result, dict) and result.get(field) == value
                       for result in matches):
                return False, "MCP response assertion not satisfied for " + tool
    return True, "Required tool calls and outcomes observed"


async def agent_turn(http, mcp_client, messages, tools, case, config, called, public_turns, secrets):
    for _ in range(MAX_TURNS):
        answer = await http.post(
            config["llm"] + "/chat/completions",
            headers={"Authorization": "Bearer " + (config["api_key"] or "local-evaluation")},
            json={"model": config["model"], "messages": messages, "tools": tools,
                  "tool_choice": "auto", "temperature": 0, "stream": False},
            timeout=120,
        )
        answer.raise_for_status()
        result = answer.json()
        message = result["choices"][0]["message"]
        message = {k: message[k] for k in ("role", "content", "tool_calls") if k in message}
        message.setdefault("role", "assistant")
        messages.append(message)
        if message.get("content"):
            public_turns.append("Assistant: " + redacted(message["content"], secrets))
        calls = message.get("tool_calls") or []
        if not calls:
            return
        for tc in calls:
            if tc.get("type") != "function":
                raise ValueError("Unsupported model tool call")
            name = tc["function"]["name"]
            if name not in {item["function"]["name"] for item in tools}:
                raise ValueError("Model requested unadvertised MCP tool")
            arguments = json.loads(tc["function"].get("arguments") or "{}")
            if not isinstance(arguments, dict):
                raise ValueError("Invalid MCP tool arguments")
            if name in WRITE_TOOLS and (not config["allow_writes"] or not case["mutation"]):
                output = {"error": "Synthetic evaluation mutations are not authorized"}
            else:
                raw = await mcp_client.call_tool(name, arguments=arguments)
                try:
                    output = normalize_result(raw)
                except Exception:
                    output = {"error": "MCP tool returned an error"}
                called.append((name, output))
                public_turns.append("MCP tool invoked: " + name + " (arguments and result withheld)")
            messages.append({"role": "tool", "tool_call_id": tc["id"],
                             "content": json.dumps(output, ensure_ascii=False, default=str)[:12_000]})
    raise RuntimeError("Assistant exceeded allowed tool-call turns")


async def execute_case(case, config, conn, llm_http):
    persona = case["persona"]
    public_persona = ", ".join((str(persona["name"]), "age " + str(persona["age"]),
                                str(persona["village"]), str(persona["speaking_style"])))
    secrets = list(config["tokens"].values())
    for key in ("test_mobile", "application_no"):
        secrets.append(case["db_expectation"].get(key, ""))
    secrets += [str(x) for x in case.get("private_redactions", [])]
    result = {"id": case["id"], "persona": redacted(public_persona),
              "prompt": redacted(persona["goal"]), "conversation": [],
              "tool": "Real LLM + authenticated MCP + PostgreSQL",
              "status": "ERROR", "reason": "Evaluation did not complete"}
    called = []
    before = snapshot(conn, case["db_expectation"])
    messages = [{"role": "system", "content": (
        "You are the Seva Setu pension assistant. Use ONLY the advertised MCP tools for "
        "scheme facts or portal data. Never invent records, reference numbers, bank details "
        "or document tickets. Be concise and respectful. Respect the user's explicit "
        "confirmation or refusal. Do not claim a transaction succeeded unless a tool says so. "
        "You assist a fictional authorized test user and must never request unauthorized data."
    )}]
    try:
        endpoint = config[case["role"]]
        token = config["tokens"][case["identity"]]
        async with httpx2.AsyncClient(headers={"Authorization": "Bearer " + token},
                                      timeout=httpx2.Timeout(30.0, read=120.0)) as transport_http:
            async with Client(streamable_http_client(endpoint, http_client=transport_http)) as client:
                available = await client.list_tools()
                role_tools = list(available.tools)
                all_names = {t.name for t in role_tools}
                if case["role"] == "citizen" and (all_names & {"approve_application", "reject_application", "pending_application_queue"}):
                    raise ValueError("Officer tools are exposed to citizen MCP client")
                if case["role"] == "officer" and (all_names & {"submit_pension_application", "withdraw_my_application"}):
                    raise ValueError("Citizen mutation tools are exposed to officer MCP client")
                tools = [{"type": "function", "function": {"name": t.name,
                          "description": t.description or "", "parameters": t.input_schema}}
                         for t in role_tools]
                for text in case["user_turns"]:
                    messages.append({"role": "user", "content": text})
                    result["conversation"].append("Citizen / officer: " + redacted(text, secrets))
                    await agent_turn(llm_http, client, messages, tools, case,
                                     config, called, result["conversation"], secrets)
                tool_ok, tool_reason = assert_tool_behavior(case, called)
                db_ok, db_reason = check_db_after(conn, case["db_expectation"], before,
                                                  called, case["mutation"])
                result["status"] = "PASS" if tool_ok and db_ok else "FAIL"
                result["reason"] = ("Tools + DB assertions passed" if tool_ok and db_ok
                                    else "; ".join(x for x in (tool_reason if not tool_ok else "", db_reason if not db_ok else "") if x))
    except Exception as exc:
        # NEVER expose tokens, LLM responses, DB credentials or raw tool arguments.
        result["status"] = "ERROR"
        result["reason"] = "Evaluation failed (inspect private service logs)"
        print(case["id"], "ERROR", type(exc).__name__, file=sys.stderr)
    result["conversation"] = result["conversation"][:45]
    return result


def publish_report(report):
    folder = Path(os.environ.get("EVAL_PUBLIC_REPORT_DIR", "/var/sewasetu/eval-public"))
    if folder.is_symlink():
        raise RuntimeError("Public reports directory must not be a symlink")
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = folder / (report["run_id"] + ".json")
    output = json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8")
    if len(output) > 290_000:
        raise ValueError("Report exceeds public dashboard size limit")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(output)
    return target


async def run(path):
    config = configuration()
    cases = load_cases(path)
    if any(c["mutation"] for c in cases) and not config["allow_writes"]:
        raise ValueError("Write cases require explicit EVAL_ENABLE_WRITES authorization")
    outcomes = []
    with closing(psycopg2.connect(host=os.getenv("DB_HOST", "db"),
                                 dbname=os.getenv("DB_NAME", "sewasetu"),
                                 user=os.getenv("DB_USER", "sewasetu"),
                                 password=os.environ["DB_PASSWORD"])) as conn:
        conn.set_session(readonly=True, autocommit=True)
        if any(c["mutation"] for c in cases):
            require_disposable_fixture(conn)
        async with httpx2.AsyncClient(timeout=120.0) as llm_http:
            for case in cases:
                outcome = await execute_case(case, config, conn, llm_http)
                outcomes.append(outcome)
                print(case["id"], outcome["status"])
    passed = sum(item["status"] == "PASS" for item in outcomes)
    failed = sum(item["status"] == "FAIL" for item in outcomes)
    errors = len(outcomes) - passed - failed
    report = {"run_id": "eval-" + uuid.uuid4().hex,
              "created_at": datetime.now(timezone.utc).isoformat(),
              "mode": "live_agent_db_verified",
              "model": config["model"],
              "summary": {"total": len(outcomes), "passed": passed, "failed": failed,
                          "errors": errors, "pass_rate": round(100 * passed / len(outcomes), 2)},
              "results": outcomes}
    destination = publish_report(report)
    print("Real-agent database-evaluation report:", destination)
    print(json.dumps(report["summary"], indent=2))
    return 0 if passed == len(outcomes) else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python eval_agent.py /app/evaluation/cases.private.json")
    sys.exit(asyncio.run(run(sys.argv[1])))
