import unittest
from unittest.mock import patch

from flask import Flask

from mtc_assistant.dashboard_auth_api import create_dashboard_auth_blueprint
from mtc_assistant.dashboard_auth_service import (
    AuthenticationFailed,
    SessionInvalid,
)


class FakeService:
    def __init__(self):
        self.logout_tokens = []

    def login(self, username, password, request_id=""):
        if username != "valid.user" or password != "valid password":
            raise AuthenticationFailed()
        return {
            "session_token": "opaque-session-token",
            "expires_at": "2026-06-14T16:00:00+00:00",
            "principal": {
                "account_id": "account-1",
                "username": "valid.user",
                "display_name": "Valid User",
                "role": "teacher",
                "class_ids": ["mtc13"],
                "capabilities": ["auth.session.read_self"],
                "session_expires_at": "2026-06-14T16:00:00+00:00",
            },
        }

    def resolve_session(self, token):
        if token != "opaque-session-token":
            raise SessionInvalid()

        class Resolved:
            def safe_principal(self):
                return {
                    "account_id": "account-1",
                    "username": "valid.user",
                    "display_name": "Valid User",
                    "role": "teacher",
                    "class_ids": ["mtc13"],
                    "capabilities": ["auth.session.read_self"],
                    "session_expires_at": "2026-06-14T16:00:00+00:00",
                }

        return Resolved()

    def logout(self, token, request_id=""):
        if not token:
            raise SessionInvalid()
        self.logout_tokens.append(token)


class DashboardAuthApiTest(unittest.TestCase):
    def setUp(self):
        self.service = FakeService()
        app = Flask(__name__)
        app.register_blueprint(
            create_dashboard_auth_blueprint(
                get_service=lambda: self.service,
                service_token_provider=lambda: "service-secret",
            )
        )
        self.client = app.test_client()

    def service_headers(self, **extra):
        return {"Authorization": "Bearer service-secret", **extra}

    def test_login_requires_service_token(self):
        response = self.client.post(
            "/api/admin/auth/login",
            json={"username": "valid.user", "password": "valid password"},
        )
        self.assertEqual(401, response.status_code)

    def test_service_token_uses_constant_time_comparison(self):
        with patch(
            "mtc_assistant.dashboard_auth_api.hmac.compare_digest",
            return_value=False,
        ) as compare:
            response = self.client.post(
                "/api/admin/auth/login",
                headers={"Authorization": "Bearer supplied-token"},
                json={
                    "username": "valid.user",
                    "password": "valid password",
                },
            )
        self.assertEqual(401, response.status_code)
        compare.assert_called_once_with("supplied-token", "service-secret")
        self.assertNotIn(
            "supplied-token", response.get_data(as_text=True)
        )
        self.assertNotIn(
            "service-secret", response.get_data(as_text=True)
        )

    def test_malformed_service_bearer_is_generic_unauthorized(self):
        responses = [
            self.client.post(
                "/api/admin/auth/login",
                headers={"Authorization": value},
                json={
                    "username": "valid.user",
                    "password": "valid password",
                },
            )
            for value in ("", "Basic value", "Bearer", "Bearer value extra")
        ]
        self.assertTrue(
            all(response.status_code == 401 for response in responses)
        )
        self.assertTrue(
            all(
                response.get_json()["error"]["code"] == "UNAUTHORIZED"
                for response in responses
            )
        )

    def test_login_returns_session_and_safe_principal(self):
        response = self.client.post(
            "/api/admin/auth/login",
            headers=self.service_headers(),
            json={"username": "valid.user", "password": "valid password"},
        )
        payload = response.get_json()["data"]
        self.assertEqual(200, response.status_code)
        self.assertEqual("opaque-session-token", payload["session_token"])
        self.assertNotIn("password_hash", str(payload))
        self.assertNotIn("service-secret", response.get_data(as_text=True))

    def test_login_failures_are_generic(self):
        responses = []
        for username, password in (
            ("invalid user", "anything here"),
            ("missing.user", "anything here"),
            ("valid.user", "wrong password"),
            ("disabled.user", "anything here"),
            ("blocked.user", "anything here"),
            ("corrupt.user", "anything here"),
        ):
            response = self.client.post(
                "/api/admin/auth/login",
                headers=self.service_headers(),
                json={"username": username, "password": password},
            )
            responses.append((response.status_code, response.get_json()))
        self.assertTrue(all(item == responses[0] for item in responses))
        self.assertEqual(401, responses[0][0])
        self.assertEqual(
            "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง",
            responses[0][1]["error"]["message"],
        )

    def test_request_id_is_sanitized(self):
        response = self.client.post(
            "/api/admin/auth/login",
            headers=self.service_headers(**{"X-Request-ID": "bad request"}),
            json={"username": "missing.user", "password": "anything here"},
        )
        self.assertEqual("", response.get_json()["error"]["request_id"])

    def test_me_requires_both_trust_layers_and_ignores_transitional_headers(self):
        transitional = self.service_headers(
            **{
                "X-MTC-Admin-Id": "legacy-admin",
                "X-MTC-Admin-Role": "super_admin",
                "X-MTC-Admin-Classes": "mtc13",
            }
        )
        self.assertEqual(401, self.client.get("/api/admin/auth/me", headers=transitional).status_code)
        self.assertEqual(
            401,
            self.client.get(
                "/api/admin/auth/me",
                headers={"X-MTC-Dashboard-Session": "opaque-session-token"},
            ).status_code,
        )
        response = self.client.get(
            "/api/admin/auth/me",
            headers=self.service_headers(
                **{"X-MTC-Dashboard-Session": "opaque-session-token"}
            ),
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("account-1", response.get_json()["data"]["principal"]["account_id"])

    def test_logout_is_idempotent_for_unknown_well_formed_token(self):
        headers = self.service_headers(
            **{"X-MTC-Dashboard-Session": "x" * 43}
        )
        first = self.client.post("/api/admin/auth/logout", headers=headers)
        second = self.client.post("/api/admin/auth/logout", headers=headers)
        self.assertEqual(200, first.status_code)
        self.assertEqual(200, second.status_code)

    def test_auth_routes_set_security_headers(self):
        responses = [
            self.client.post(
                "/api/admin/auth/login",
                headers=self.service_headers(),
                json={"username": "missing.user", "password": "anything here"},
            ),
            self.client.get(
                "/api/admin/auth/me",
                headers=self.service_headers(
                    **{"X-MTC-Dashboard-Session": "x" * 43}
                ),
            ),
            self.client.post(
                "/api/admin/auth/logout",
                headers=self.service_headers(
                    **{"X-MTC-Dashboard-Session": "x" * 43}
                ),
            ),
        ]
        for response in responses:
            self.assertEqual("no-store", response.headers["Cache-Control"])
            self.assertEqual(
                "nosniff", response.headers["X-Content-Type-Options"]
            )
            self.assertNotIn("Access-Control-Allow-Origin", response.headers)

    def test_transitional_headers_never_replace_service_authentication(self):
        headers = {
            "X-MTC-Admin-Id": "legacy-admin",
            "X-MTC-Admin-Role": "super_admin",
            "X-MTC-Admin-Classes": "mtc13",
            "X-MTC-Dashboard-Session": "x" * 43,
        }
        self.assertEqual(
            401,
            self.client.post(
                "/api/admin/auth/login",
                headers=headers,
                json={"username": "valid.user", "password": "valid password"},
            ).status_code,
        )
        self.assertEqual(
            401,
            self.client.get("/api/admin/auth/me", headers=headers).status_code,
        )
        self.assertEqual(
            401,
            self.client.post(
                "/api/admin/auth/logout", headers=headers
            ).status_code,
        )

    def test_logout_uses_header_token_and_ignores_json_body(self):
        header_token = "h" * 43
        body_token = "b" * 43
        response = self.client.post(
            "/api/admin/auth/logout",
            headers=self.service_headers(
                **{"X-MTC-Dashboard-Session": header_token}
            ),
            json={"session_token": body_token},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual([header_token], self.service.logout_tokens)
        self.assertNotIn(body_token, response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
