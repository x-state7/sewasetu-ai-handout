"""Offline regression tests: run with production requirements installed.

cd app && PYTHONPATH=. python -m unittest discover -s ../tests -p 'test_eval_agent.py' -v
No database/HTTP calls are made.
"""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from eval_agent import (
    WRITE_CONFIRMATION,
    agent_turn,
    assert_tool_behavior,
    check_db_after,
    load_cases,
    redacted,
)
from eval_client import normalize_result, EvaluationClientError


class DummyLLMResponse:
    def __init__(self, message):
        self.message = message

    def raise_for_status(self):
        pass

    def json(self):
        return {"choices": [{"message": self.message}]}


class FakeHTTP:
    def __init__(self, messages):
        self.responses = list(messages)

    async def post(self, *args, **kwargs):
        return DummyLLMResponse(self.responses.pop(0))


class FakeMCP:
    def __init__(self):
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return SimpleNamespace(is_error=False, structured_content={"found": False}, content=[])


class EvaluationTests(unittest.TestCase):
    def test_sdk_snake_case_success_and_error(self):
        self.assertEqual(normalize_result(SimpleNamespace(
            is_error=False, structured_content={"status": "ok"}, content=[]
        )), {"status": "ok"})
        with self.assertRaises(EvaluationClientError):
            normalize_result(SimpleNamespace(
                is_error=True, structured_content=None, content=[]
            ))

    def test_sample_cases_are_validated(self):
        source = Path(__file__).resolve().parents[1] / "app/evaluation/cases.example.json"
        cases = load_cases(source)
        self.assertEqual(len(cases), 6)
        self.assertEqual([c["id"] for c in cases], ["C01", "C02", "C03", "O01", "O02", "C04"])
        self.assertTrue(any(c["mutation"] for c in cases))
        self.assertTrue(all(c["db_expectation"].get("expected_status") for c in cases))

    def test_sensitive_data_redaction(self):
        sample = "Mobile 9876543210 account 999000000000 IFSC SBIN0003077 ticket abcdefghijklmnopqrstuvwxyz012345"
        result = redacted(sample)
        for secret in ("9876543210", "999000000000", "SBIN0003077", "abcdefghijklmnopqrstuvwxyz012345"):
            self.assertNotIn(secret, result)

    def test_required_tool_and_security_assertions(self):
        case = {"required_tools": ["get_my_application_status"],
                "tool_assertions": [{"tool": "get_my_application_status", "field": "found", "equals": False}]}
        self.assertTrue(assert_tool_behavior(case, [("get_my_application_status", {"found": False})])[0])
        self.assertFalse(assert_tool_behavior(case, [("get_my_application_status", {"found": True})])[0])
        self.assertFalse(assert_tool_behavior(case, [])[0])

    def test_write_requires_fresh_database_change(self):
        db = {"application_no": "DEMO000001", "test_mobile": "0000000001", "expected_status": "WITHDRAWN"}
        same = {"total": 1, "newest_id": 1, "status": "WITHDRAWN", "audit": {"WITHDRAW": 1}}
        with patch("eval_agent.verify", return_value=(True, "passed")), patch("eval_agent.snapshot", return_value=same):
            ok, reason = check_db_after(None, db, same, [], True)
        self.assertFalse(ok)
        self.assertIn("No new persisted", reason)

    def test_read_only_rejects_mutations(self):
        db = {"application_no": "DEMO000001", "test_mobile": "0000000001", "expected_status": "PENDING"}
        original = {"total": 1, "newest_id": 1, "status": "PENDING", "audit": {"SUBMIT": 1}}
        changed = {"total": 1, "newest_id": 1, "status": "APPROVED", "audit": {"SUBMIT": 1}}
        with patch("eval_agent.verify", return_value=(True, "passed")), patch("eval_agent.snapshot", return_value=changed):
            self.assertFalse(check_db_after(None, db, original, [], False)[0])

    def test_submission_requires_actual_mcp_reference(self):
        db = {"test_mobile": "0000000002", "expected_status": "PENDING"}
        baseline = {"total": 1, "newest_id": 2, "status": None, "audit": {}}
        with patch("eval_agent.verify", return_value=(True, "passed")):
            self.assertFalse(check_db_after(None, db, baseline, [], True)[0])
            self.assertFalse(check_db_after(None, db, baseline,
                [("submit_pension_application", {"status": "invalid"})], True)[0])

    def test_real_tool_turn_invokes_mcp_and_redacts_public_log(self):
        async def run():
            call = {"id": "call_01", "type": "function", "function": {
                "name": "get_my_application_status", "arguments": json.dumps({"application_no": "DEMO000001"})}}
            http = FakeHTTP([{"role": "assistant", "content": None, "tool_calls": [call]},
                             {"role": "assistant", "content": "I cannot view another citizen's record."}])
            mcp = FakeMCP()
            messages = [{"role": "system", "content": "Test"}, {"role": "user", "content": "Please find record"}]
            calls, public = [], []
            await agent_turn(http, mcp, messages, [
                {"type": "function", "function": {"name": "get_my_application_status"}}
            ], {"mutation": False}, {"llm": "https://example.invalid/v1", "model": "test", "api_key": "", "allow_writes": False},
                calls, public, [])
            return mcp.calls, calls, public
        mcp_calls, calls, public = asyncio.run(run())
        self.assertEqual(mcp_calls, [("get_my_application_status", {"application_no": "DEMO000001"})])
        self.assertEqual(calls[0][1], {"found": False})
        self.assertIn("MCP tool invoked", " ".join(public))
        self.assertNotIn("DEMO000001", " ".join(public))

    def test_mutation_tool_blocked_without_authorization(self):
        async def run():
            call = {"id": "call_1", "type": "function", "function": {
                "name": "approve_application", "arguments": '{"application_no":"DEMO000001","confirm_decision":true}'}}
            http = FakeHTTP([{"role": "assistant", "tool_calls": [call]}, {"role": "assistant", "content": "Cannot do that"}])
            mcp = FakeMCP()
            calls, public = [], []
            await agent_turn(http, mcp, [{"role": "system", "content": "Test"}],
                [{"type": "function", "function": {"name": "approve_application"}}],
                {"mutation": True}, {"llm": "https://example.invalid/v1", "model": "x", "api_key": "", "allow_writes": False},
                calls, public, [])
            return mcp.calls, calls
        self.assertEqual(asyncio.run(run()), ([], []))


if __name__ == "__main__":
    unittest.main()
