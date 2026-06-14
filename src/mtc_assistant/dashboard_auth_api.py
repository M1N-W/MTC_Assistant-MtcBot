"""HTTP adapter for Flask-owned dashboard authentication."""

from __future__ import annotations

import hmac
import re
from typing import Any, Callable

from flask import Blueprint, jsonify, request

from mtc_assistant.dashboard_auth_service import (
    AuthenticationFailed,
    DashboardAuthService,
    SessionInvalid,
)


GENERIC_LOGIN_MESSAGE = "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
SESSION_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def create_dashboard_auth_blueprint(
    get_service: Callable[[], DashboardAuthService],
    service_token_provider: Callable[[], str],
) -> Blueprint:
    blueprint = Blueprint(
        "dashboard_auth_api", __name__, url_prefix="/api/admin/auth"
    )

    @blueprint.after_request
    def security_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @blueprint.before_request
    def require_service_authentication():
        configured = service_token_provider()
        if not configured:
            return _error(
                "DASHBOARD_NOT_CONFIGURED",
                "Dashboard API token is not configured.",
                503,
            )
        authorization = request.headers.get("Authorization", "")
        scheme, separator, provided = authorization.partition(" ")
        if (
            scheme != "Bearer"
            or separator != " "
            or not provided
            or " " in provided
            or not hmac.compare_digest(provided, configured)
        ):
            return _error(
                "UNAUTHORIZED",
                "Missing or invalid dashboard API token.",
                401,
            )
        return None

    @blueprint.post("/login")
    def login():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _error("VALIDATION_ERROR", GENERIC_LOGIN_MESSAGE, 401)
        try:
            result = get_service().login(
                payload.get("username"),
                payload.get("password"),
                request_id=_request_id(),
            )
        except AuthenticationFailed:
            return _error("UNAUTHORIZED", GENERIC_LOGIN_MESSAGE, 401)
        except Exception:
            return _error(
                "AUTH_SERVICE_UNAVAILABLE",
                "ระบบยืนยันตัวตนไม่พร้อมใช้งานในขณะนี้",
                503,
            )
        return jsonify({"data": result}), 200

    @blueprint.get("/me")
    def current_principal():
        token = request.headers.get("X-MTC-Dashboard-Session", "")
        try:
            resolved = get_service().resolve_session(token)
        except SessionInvalid:
            return _error(
                "UNAUTHORIZED", "Dashboard session is required.", 401
            )
        except Exception:
            return _error(
                "AUTH_SERVICE_UNAVAILABLE",
                "ระบบยืนยันตัวตนไม่พร้อมใช้งานในขณะนี้",
                503,
            )
        return jsonify({"data": {"principal": resolved.safe_principal()}}), 200

    @blueprint.post("/logout")
    def logout():
        token = request.headers.get("X-MTC-Dashboard-Session", "")
        if not isinstance(token, str) or not SESSION_TOKEN_PATTERN.fullmatch(token):
            return _error(
                "UNAUTHORIZED", "Dashboard session is required.", 401
            )
        try:
            get_service().logout(token, request_id=_request_id())
        except SessionInvalid:
            pass
        except Exception:
            return _error(
                "AUTH_SERVICE_UNAVAILABLE",
                "ระบบยืนยันตัวตนไม่พร้อมใช้งานในขณะนี้",
                503,
            )
        return jsonify({"data": {"status": "signed_out"}}), 200

    return blueprint


def _error(code: str, message: str, status: int):
    return (
        jsonify(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": _request_id(),
                }
            }
        ),
        status,
    )


def _request_id() -> str:
    value = request.headers.get("X-Request-ID", "")
    return value if REQUEST_ID_PATTERN.fullmatch(value) else ""
