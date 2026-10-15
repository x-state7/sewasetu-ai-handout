"""Offline tests for Day 1 / Step 2. Run: python -m unittest discover -s tests -v"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from application_service import submit_application


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params):
        self.conn.events.append(("lock", params[0]))
        assert "pg_advisory_xact_lock" in sql


class FakeConnection:
    def __init__(self):
        self.events = []
        self.closed = False

    def __enter__(self):
        self.events.append(("begin",))
        return self

    def __exit__(self, exc_type, exc, tb):
        self.events.append(("rollback" if exc_type else "commit",))
        return False

    def cursor(self):
        return FakeCursor(self)

    def close(self):
        self.closed = True


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.conn = FakeConnection()
        self.creates = []
        self.data = {"applicant_name": "Saraswati"}
        self.mobile = "9999999999"

    def go(self, *, errors=(), existing=None, fail=False):
        def check(data, doc_path):
            self.conn.events.append(("validate", doc_path))
            return list(errors), {"applicant_name": "Saraswati"}

        def active(cur, mobile):
            self.conn.events.append(("lookup", mobile))
            return existing

        def insert(cur, mobile, data):
            self.conn.events.append(("insert", mobile))
            if fail:
                raise RuntimeError("database write failed")
            self.creates.append(mobile)
            return 100001, "SSP2600100001"

        return submit_application(
            self.mobile, self.data, "/tmp/proof.pdf",
            connect=lambda: self.conn, validate=check,
            find_active=active, insert=insert,
        )

    def test_success_and_order(self):
        result = self.go()
        self.assertEqual(result.status, "submitted")
        self.assertEqual(result.application_no, "SSP2600100001")
        self.assertEqual([x[0] for x in self.conn.events],
                         ["begin", "lock", "validate", "lookup", "insert", "commit"])
        self.assertEqual(self.creates, [self.mobile])
        self.assertTrue(self.conn.closed)

    def test_existing_skips_insert(self):
        result = self.go(existing=(25, "SSP26123456", "PENDING"))
        self.assertEqual(result.status, "existing")
        self.assertEqual(result.application_id, 25)
        self.assertEqual(self.creates, [])
        self.assertTrue(self.conn.closed)

    def test_invalid_does_not_insert(self):
        result = self.go(errors=["proof required", "age below 60"])
        self.assertEqual(result.status, "invalid")
        self.assertEqual(len(result.errors), 2)
        self.assertNotIn(("lookup", self.mobile), self.conn.events)
        self.assertEqual(self.creates, [])

    def test_exception_rolls_back_and_closes(self):
        with self.assertRaises(RuntimeError):
            self.go(fail=True)
        self.assertIn(("rollback",), self.conn.events)
        self.assertTrue(self.conn.closed)

    def test_mobile_must_be_verified_format(self):
        self.mobile = ""
        with self.assertRaises(ValueError):
            self.go()
        self.assertEqual(self.conn.events, [])


if __name__ == "__main__":
    unittest.main()
