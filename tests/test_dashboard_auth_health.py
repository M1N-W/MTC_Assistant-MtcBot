import unittest
from unittest.mock import patch

import mtc_assistant.main as main


class DashboardAuthHealthTest(unittest.TestCase):
    def test_main_app_auth_route_uses_configured_service_token(self):
        class FakeService:
            def login(self, username, password, request_id=""):
                return {
                    "session_token": "x" * 43,
                    "expires_at": "2026-06-14T16:00:00+00:00",
                    "principal": {
                        "account_id": "account-1",
                        "username": "fake.user",
                        "display_name": None,
                        "role": "teacher",
                        "class_ids": ["mtc13"],
                        "capabilities": ["auth.session.read_self"],
                        "session_expires_at": "2026-06-14T16:00:00+00:00",
                    },
                }

        with (
            patch.object(main, "_ensure_firebase_connected", return_value=None),
            patch.object(main, "MTC_DASHBOARD_API_TOKEN", "service-secret"),
            patch.object(main, "dashboard_auth_service", FakeService()),
        ):
            response = main.app.test_client().post(
                "/api/admin/auth/login",
                headers={"Authorization": "Bearer service-secret"},
                json={"username": "fake.user", "password": "fake password"},
            )
        self.assertEqual(200, response.status_code)

    def test_audit_failure_degrades_only_security_audit_subsystem(self):
        class FakeQuery:
            def limit(self, count):
                return self

            def stream(self):
                return iter(())

        class FakeDb:
            def collection(self, name):
                return FakeQuery()

        original_state = main.dashboard_security_audit_state
        try:
            main.dashboard_security_audit_state = type(original_state)()
            main.dashboard_security_audit_state.record_failure()
            with (
                patch.object(
                    main, "_ensure_firebase_connected", return_value=FakeDb()
                ),
                patch.object(main, "ACCESS_TOKEN", "line-token"),
                patch.object(main, "CHANNEL_SECRET", "line-secret"),
                patch.object(main, "GEMINI_API_KEY_V3", "gemini-key"),
                patch.object(main, "gemini_client_v3", object()),
                patch.object(main, "line_config", object()),
                patch.object(main, "db", FakeDb()),
            ):
                response = main.app.test_client().get("/healthz")
        finally:
            main.dashboard_security_audit_state = original_state

        payload = response.get_json()
        self.assertEqual(200, response.status_code)
        self.assertEqual("degraded", payload["status"])
        self.assertTrue(payload["services"]["line"])
        self.assertTrue(payload["services"]["firebase"])
        self.assertTrue(payload["services"]["firebase_connectivity"])
        self.assertTrue(payload["services"]["gemini"])
        self.assertTrue(payload["services"]["broadcast"])
        self.assertFalse(payload["services"]["security_audit"])

    def test_metrics_expose_audit_and_unknown_login_counters_separately(self):
        original_state = main.dashboard_security_audit_state
        try:
            main.dashboard_security_audit_state = type(original_state)()
            main.dashboard_security_audit_state.record_failure()
            main.dashboard_security_audit_state.record_unknown_login_failure()
            snapshot = main._metrics_snapshot()
        finally:
            main.dashboard_security_audit_state = original_state
        self.assertEqual(1, snapshot["security_audit_write_failures"])
        self.assertEqual(1, snapshot["unknown_login_failures"])
        self.assertFalse(snapshot["security_audit"])


if __name__ == "__main__":
    unittest.main()
