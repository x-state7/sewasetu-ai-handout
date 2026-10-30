"""Security regression tests for reviewer-only OAuth and synthetic OTP viewer.

Run from app/ with: PYTHONPATH=. python -m unittest discover -s ../tests -p 'test_reviewer_access.py' -v
Most helper tests need only the standard library. Flask integration tests need the app requirements.
"""
import os
import time
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from reviewer_access import (allowed_test_mobiles, check_otp_reviewer,
                             delivered_otp, officer_subject, otp_reviewer_enabled)

CONFIG = {
    "ADMIN_USERNAME": "admin",
    "ADMIN_PASSWORD": "A" * 32,
    "OFFICER_REVIEWER_USERNAME": "reviewer-officer",
    "OFFICER_REVIEWER_PASSWORD": "B" * 32,
    "REVIEWER_OTP_USERNAME": "reviewer-otp",
    "REVIEWER_OTP_PASSWORD": "C" * 32,
    "REVIEWER_OTP_MOBILES": "0000000001,0000000002,0000000008",
}


class ReviewerCredentialTests(unittest.TestCase):
    def test_officer_auth_does_not_become_admin(self):
        self.assertEqual(officer_subject("reviewer-officer", "B" * 32, CONFIG), "officer:reviewer-officer")
        self.assertEqual(officer_subject("admin", "A" * 32, CONFIG), "officer:admin")
        self.assertIsNone(officer_subject("reviewer-officer", "A" * 32, CONFIG))
        self.assertIsNone(officer_subject("admin", "B" * 32, CONFIG))
        self.assertIsNone(officer_subject("reviewer-officer", "", CONFIG))

    def test_reviewer_username_cannot_shadow_admin(self):
        env = dict(CONFIG, OFFICER_REVIEWER_USERNAME="admin")
        self.assertIsNone(officer_subject("admin", "B" * 32, env))

    def test_synthetic_otp_whitelist_is_strict(self):
        self.assertEqual(allowed_test_mobiles(CONFIG),
                         ("0000000001", "0000000002", "0000000008"))
        self.assertFalse(allowed_test_mobiles(dict(CONFIG, REVIEWER_OTP_MOBILES="9876543210")))
        self.assertFalse(allowed_test_mobiles(dict(CONFIG, REVIEWER_OTP_MOBILES="0000000001,0000000001")))
        self.assertFalse(allowed_test_mobiles(dict(CONFIG, REVIEWER_OTP_MOBILES="0000000013")))
        self.assertFalse(otp_reviewer_enabled(dict(CONFIG, REVIEWER_OTP_PASSWORD="short")))
        self.assertFalse(check_otp_reviewer("reviewer-otp", "wrong", CONFIG))
        self.assertTrue(check_otp_reviewer("reviewer-otp", "C" * 32, CONFIG))

    def test_reveals_only_delivered_otp_for_selected_mobile(self):
        payload = {"messages": [
            {"to": "0000000001", "text": "Your Sewa Setu OTP is 234567. Valid for 5 minutes.",
             "delivered": True, "sent_at": 100},
            {"to": "0000000001", "text": "Your Sewa Setu OTP is 345678. Valid for 5 minutes.",
             "delivered": False, "sent_at": 200},
            {"to": "0000000002", "text": "Your Sewa Setu OTP is 999999. Valid for 5 minutes.",
             "delivered": True, "sent_at": 300},
        ]}
        self.assertEqual(delivered_otp(payload, "0000000001", now=200), "234567")
        self.assertEqual(delivered_otp(payload, "0000000002", now=350), "999999")
        self.assertIsNone(delivered_otp(payload, "0000000008", now=350))
        self.assertIsNone(delivered_otp({"messages": "not a list"}, "0000000001"))


try:
    import flask  # noqa: F401
    import psycopg2  # noqa: F401
    import requests  # noqa: F401
    import mcp  # noqa: F401
except ImportError:
    HAS_APP_DEPS = False
else:
    HAS_APP_DEPS = True


@unittest.skipUnless(HAS_APP_DEPS, "Install app/requirements.txt to run Flask route checks")
class ReviewerRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.environ = patch.dict(os.environ, {**CONFIG,
            "SECRET_KEY": "D" * 64, "PUBLIC_BASE_URL": "http://localhost:8000", "DB_PASSWORD": "test-only"})
        cls.environ.start()
        from app import app
        cls.app = app
        cls.app.testing = True

    @classmethod
    def tearDownClass(cls):
        cls.environ.stop()

    def setUp(self):
        self.client = self.app.test_client()

    def _csrf(self):
        with self.client.session_transaction() as sess:
            return sess["_csrf_token"]

    def _sign_in(self):
        self.client.get("/reviewer/otp/login")
        return self.client.post("/reviewer/otp/login", data={
            "_csrf_token": self._csrf(),
            "username": "reviewer-otp", "password": "C" * 32,
        }, follow_redirects=True)

    def test_viewer_requires_login_and_never_grants_admin(self):
        first = self.client.get("/reviewer/otp")
        self.assertEqual(first.status_code, 302)
        resp = self._sign_in()
        self.assertEqual(resp.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertTrue(sess.get("reviewer_otp"))
            self.assertFalse(sess.get("admin", False))
        self.assertEqual(self.client.get("/admin/dashboard").status_code, 302)

    def test_out_of_scope_mobile_is_rejected_without_gateway_call(self):
        self._sign_in()
        with patch("app.requests.get") as gateway:
            resp = self.client.post("/reviewer/otp", data={
                "_csrf_token": self._csrf(), "mobile": "9876543210"})
            self.assertEqual(resp.status_code, 403)
            gateway.assert_not_called()

    def test_reviewer_receives_only_delivered_synthetic_otp(self):
        self._sign_in()
        self.client.post("/reviewer/otp", data={
            "_csrf_token": self._csrf(), "mobile": "0000000001"})
        mock_response = SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"messages": [
                {"to": "0000000001", "text": "Your Sewa Setu OTP is 123456. Valid for 5 minutes.",
                 "delivered": True, "sent_at": time.time()},
            ]})
        with patch("app.requests.get", return_value=mock_response) as gateway:
            resp = self.client.get("/reviewer/otp")
        self.assertIn(b"123456", resp.data)
        self.assertEqual(resp.headers["Cache-Control"], "no-store")
        self.assertEqual(gateway.call_args.kwargs["params"], {"to": "0000000001"})


if __name__ == "__main__":
    unittest.main()
