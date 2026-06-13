# -*- coding: utf-8 -*-
"""
Admin API for the MTC Assistant web dashboard.

The LINE webhook remains independent from this blueprint.  Dashboard requests
must carry a server-side bearer token; the browser never receives that token.
"""

from __future__ import annotations

import datetime
import base64
import binascii
import os
import re
import threading
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple

from flask import Blueprint, g, jsonify, request
from firebase_admin import firestore
from werkzeug.exceptions import HTTPException

import mtc_assistant.broadcast as broadcast
from mtc_assistant.ai_credential_service import (
    AICredentialService,
    build_credential_cipher_from_env,
    system_credentials_from_env,
)
from mtc_assistant.ai_provider_adapters import AIProviderError
from mtc_assistant.ai_provider_registry import get_provider_definition
from mtc_assistant.class_context import get_class_registry_entry
from mtc_assistant.config import (
    DASHBOARD_ALLOWED_ORIGINS,
    LOCAL_TZ,
    MTC_DASHBOARD_API_TOKEN,
    MTC_EXPECTED_CLASS_SIZE,
    PAPER_CO2_GRAMS_PER_SHEET,
    logger,
)
from mtc_assistant.paperless_capture import (
    ALLOWED_IMAGE_MIME_TYPES,
    MAX_IMAGE_BYTES,
    PaperlessCaptureError,
    analyze_classroom_image,
)
from mtc_assistant.invite_codes import is_valid_class_id
from mtc_assistant.links_service import LINK_KEYS, get_safe_fallback_links, merge_link_values
from mtc_assistant.user_blacklist import get_blacklist_manager


DbProvider = Callable[[], Any]
MetricsProvider = Callable[[], Dict[str, Any]]
CredentialServiceProvider = Callable[[Any], AICredentialService]
TERM_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
SECRET_VALUE_PATTERN = re.compile(
    r"(api[_-]?key|bearer|private[_-]?key|secret|token|MTC_[A-Z0-9_]*|LINE_CHANNEL|GEMINI)",
    re.IGNORECASE,
)
LOCAL_PATH_PATTERN = re.compile(r"^([A-Za-z]:\\|/Users/|/home/|/|\.{1,2}[/\\]|~[/\\])")


@dataclass(frozen=True)
class DashboardPrincipal:
    admin_id: str
    role: str
    class_ids: frozenset[str]
    authenticated: bool


def create_admin_api_blueprint(
    get_db: DbProvider,
    get_metrics: MetricsProvider,
    get_services: Callable[[], Dict[str, Any]],
    get_ai_credential_service: CredentialServiceProvider | None = None,
) -> Blueprint:
    blueprint = Blueprint("admin_api", __name__, url_prefix="/api/admin")
    credential_service_provider = (
        get_ai_credential_service or _default_ai_credential_service
    )

    @blueprint.after_request
    def add_api_headers(response):
        origin = request.headers.get("Origin", "")
        if origin and origin in DASHBOARD_ALLOWED_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = (
                "Authorization, Content-Type, X-MTC-Admin-Id, "
                "X-MTC-Admin-Role, X-MTC-Admin-Classes"
            )
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @blueprint.before_request
    def authenticate_dashboard_request():
        if request.method == "OPTIONS":
            return "", 204
        if not MTC_DASHBOARD_API_TOKEN:
            return _error("DASHBOARD_NOT_CONFIGURED", "Dashboard API token is not configured.", 503)
        auth_header = request.headers.get("Authorization", "")
        expected = f"Bearer {MTC_DASHBOARD_API_TOKEN}"
        if auth_header != expected:
            return _error("UNAUTHORIZED", "Missing or invalid dashboard API token.", 401)
        g.dashboard_principal = _dashboard_principal_from_headers()
        return None

    @blueprint.errorhandler(Exception)
    def handle_admin_api_exception(error):
        if isinstance(error, HTTPException):
            status = error.code or 500
            return _error(f"HTTP_{status}", error.description or "Dashboard API request failed.", status)
        logger.exception("Dashboard API unhandled error: %s", error)
        return _error("INTERNAL_ERROR", "Dashboard API request failed.", 500)

    @blueprint.get("/overview")
    def overview():
        db = get_db()
        metrics = get_metrics()
        services = get_services()
        homework_items = _get_recent_homeworks(db, limit=6)
        blacklist = get_blacklist_manager().get_all_banned()
        recent_broadcasts = _get_recent_broadcasts(db, limit=5)
        sustainability = _build_sustainability_impact(db, metrics)

        return jsonify({
            "data": {
                "generated_at": _now_iso(),
                "services": services,
                "metrics": metrics,
                "counts": {
                    "registered_users": broadcast.get_user_count() if db else 0,
                    "rate_limit_tracked_users": metrics.get("rate_limit_tracked_users", 0),
                    "active_homework_preview": len(homework_items),
                    "banned_users": len(blacklist),
                    "recent_broadcasts": len(recent_broadcasts),
                },
                "sustainability": sustainability,
                "homework_preview": homework_items,
                "recent_broadcasts": recent_broadcasts,
            }
        }), 200

    @blueprint.get("/sustainability")
    def sustainability():
        db = get_db()
        return jsonify({
            "data": _build_sustainability_impact(db, get_metrics())
        }), 200

    @blueprint.post("/paperless-capture")
    def paperless_capture():
        image_bytes, mime_type, error = _image_body()
        if error:
            return error

        try:
            analysis = analyze_classroom_image(image_bytes, mime_type)
        except PaperlessCaptureError as e:
            return _error("PAPERLESS_CAPTURE_FAILED", str(e), 422)
        except Exception as e:
            logger.exception("Paperless capture failed: %s", e)
            return _error("PAPERLESS_CAPTURE_FAILED", "Could not analyze this image.", 500)

        db = get_db()
        if db:
            try:
                db.collection("paperless_captures").add({
                    "mime_type": mime_type,
                    "image_size_bytes": len(image_bytes),
                    "analysis": analysis,
                    "created_at": datetime.datetime.now(tz=LOCAL_TZ).isoformat(),
                    "timestamp": firestore.SERVER_TIMESTAMP,
                })
            except Exception as e:
                logger.warning("Could not save paperless capture history: %s", e)

        return jsonify({
            "data": {
                "analysis": analysis,
                "image_size_bytes": len(image_bytes),
                "mime_type": mime_type,
            }
        }), 200

    @blueprint.get("/users")
    def users():
        limit, offset = _pagination(default_limit=50, max_limit=100)
        user_ids = broadcast.get_all_users()
        page = user_ids[offset:offset + limit]
        return jsonify({
            "data": {
                "items": [{"user_id": user_id} for user_id in page],
                "page": {
                    "limit": limit,
                    "offset": offset,
                    "total": len(user_ids),
                    "has_next": offset + limit < len(user_ids),
                },
            }
        }), 200

    @blueprint.get("/homeworks")
    def homeworks():
        db = get_db()
        if not db:
            return _error("FIREBASE_UNAVAILABLE", "Firebase is not connected.", 503)
        limit, _offset = _pagination(default_limit=30, max_limit=100)
        return jsonify({"data": {"items": _get_recent_homeworks(db, limit=limit)}}), 200

    @blueprint.get("/broadcasts")
    def broadcasts():
        db = get_db()
        if not db:
            return _error("FIREBASE_UNAVAILABLE", "Firebase is not connected.", 503)
        limit, _offset = _pagination(default_limit=20, max_limit=50)
        return jsonify({"data": {"items": _get_recent_broadcasts(db, limit=limit)}}), 200

    @blueprint.post("/broadcasts")
    def create_broadcast():
        payload, error = _json_body()
        if error:
            return error
        message = str(payload.get("message", "")).strip()
        title = str(payload.get("title", "ประกาศจากผู้ดูแล")).strip() or "ประกาศจากผู้ดูแล"
        if not message:
            return _error("VALIDATION_ERROR", "message is required.", 422)
        if len(message) > 1000:
            return _error("VALIDATION_ERROR", "message must be 1000 characters or fewer.", 422)

        announcement = broadcast.create_announcement(title, message)

        def _send_in_background():
            result = broadcast.broadcast_message(announcement)
            broadcast.save_broadcast_history("dashboard", announcement, result)
            logger.info("Dashboard broadcast complete: %s", result.get("message"))

        threading.Thread(target=_send_in_background, daemon=True).start()
        return jsonify({
            "data": {
                "status": "queued",
                "queued_at": _now_iso(),
                "message": "Broadcast queued in background.",
            }
        }), 202

    @blueprint.get("/classes/<class_id>/terms/<term_id>/config/links")
    def class_term_links(class_id: str, term_id: str):
        db = get_db()
        validation_error = _validate_links_target(db, class_id, term_id)
        if validation_error:
            return validation_error

        doc = _links_doc_ref(db, class_id, term_id).get()
        data = doc.to_dict() if getattr(doc, "exists", False) else {}
        links = _extract_links(data or {})
        return jsonify({
            "data": _links_response(class_id, term_id, links, data or {})
        }), 200

    @blueprint.put("/classes/<class_id>/terms/<term_id>/config/links")
    def update_class_term_links(class_id: str, term_id: str):
        db = get_db()
        validation_error = _validate_links_target(db, class_id, term_id)
        if validation_error:
            return validation_error

        payload, error = _json_body()
        if error:
            return error
        links, error = _validate_links_payload(payload)
        if error:
            return error

        updated_at = _now_iso()
        updated_by = "dashboard"
        doc_ref = _links_doc_ref(db, class_id, term_id)
        doc_ref.set({
            **links,
            "updated_at": updated_at,
            "updated_by": updated_by,
        }, merge=True)

        doc = doc_ref.get()
        data = doc.to_dict() if getattr(doc, "exists", False) else {}
        response_links = _extract_links(data or links)
        return jsonify({
            "data": _links_response(
                class_id,
                term_id,
                response_links,
                data or {"updated_at": updated_at, "updated_by": updated_by},
            )
        }), 200

    @blueprint.get("/blacklist")
    def blacklist():
        manager = get_blacklist_manager()
        items = [
            {
                "user_id": record.user_id,
                "banned_at": record.banned_at,
                "banned_by": record.banned_by,
                "reason": record.reason,
                "is_permanent": record.is_permanent,
            }
            for record in manager.get_all_banned().values()
        ]
        return jsonify({"data": {"items": items, "total": len(items)}}), 200

    @blueprint.post("/blacklist")
    def ban_user():
        payload, error = _json_body()
        if error:
            return error
        user_id = str(payload.get("user_id", "")).strip()
        reason = str(payload.get("reason", "Dashboard ban")).strip() or "Dashboard ban"
        if not user_id:
            return _error("VALIDATION_ERROR", "user_id is required.", 422)
        if len(reason) > 240:
            return _error("VALIDATION_ERROR", "reason must be 240 characters or fewer.", 422)

        success = get_blacklist_manager().ban_user(user_id, "dashboard", reason)
        if not success:
            return _error("BLACKLIST_WRITE_FAILED", "Could not ban this user.", 500)
        return jsonify({"data": {"user_id": user_id, "status": "banned"}}), 201

    @blueprint.delete("/blacklist/<user_id>")
    def unban_user(user_id: str):
        success = get_blacklist_manager().unban_user(user_id)
        if not success:
            return _error("NOT_FOUND", "User is not currently banned.", 404)
        return jsonify({"data": {"user_id": user_id, "status": "unbanned"}}), 200

    @blueprint.get("/classes/<class_id>/ai/credentials")
    def class_ai_credentials(class_id: str):
        access_error = _require_class_admin_access(class_id)
        if access_error:
            return access_error
        db = get_db()
        service, service_error = _get_ai_credential_service(
            db,
            credential_service_provider,
        )
        if service_error:
            return service_error
        return jsonify({
            "data": {
                "class_id": class_id,
                "providers": service.list_class_credentials(class_id),
                "settings": _get_ai_settings(db, class_id),
            }
        }), 200

    @blueprint.post("/classes/<class_id>/ai/credentials/<provider_id>/validate")
    def validate_class_ai_credential(class_id: str, provider_id: str):
        access_error = _require_class_admin_access(class_id)
        if access_error:
            return access_error
        payload, error = _json_body()
        if error:
            return error
        api_key, model, error = _validate_credential_payload(provider_id, payload)
        if error:
            return error
        service, service_error = _get_ai_credential_service(
            get_db(),
            credential_service_provider,
        )
        if service_error:
            return service_error
        try:
            result = service.validate_credential(provider_id, api_key, model)
        except AIProviderError as exc:
            return _error("AI_CREDENTIAL_INVALID", str(exc), 422)
        return jsonify({"data": result}), 200

    @blueprint.put("/classes/<class_id>/ai/credentials/<provider_id>")
    def save_class_ai_credential(class_id: str, provider_id: str):
        access_error = _require_class_admin_access(class_id)
        if access_error:
            return access_error
        payload, error = _json_body()
        if error:
            return error
        if payload.get("status") == "disabled":
            service, service_error = _get_ai_credential_service(
                get_db(),
                credential_service_provider,
            )
            if service_error:
                return service_error
            try:
                disabled = service.disable_class_credential(
                    class_id,
                    provider_id,
                    actor_id=g.dashboard_principal.admin_id,
                )
            except ValueError as exc:
                return _error("VALIDATION_ERROR", str(exc), 422)
            return jsonify({"data": disabled}), 200
        api_key, model, error = _validate_credential_payload(provider_id, payload)
        if error:
            return error
        service, service_error = _get_ai_credential_service(
            get_db(),
            credential_service_provider,
        )
        if service_error:
            return service_error
        try:
            service.validate_credential(provider_id, api_key, model)
            saved = service.save_class_credential(
                class_id,
                provider_id,
                api_key,
                model=model,
                actor_id=g.dashboard_principal.admin_id,
            )
        except AIProviderError as exc:
            return _error("AI_CREDENTIAL_INVALID", str(exc), 422)
        except ValueError as exc:
            return _error("VALIDATION_ERROR", str(exc), 422)
        return jsonify({"data": saved}), 200

    @blueprint.delete("/classes/<class_id>/ai/credentials/<provider_id>")
    def delete_class_ai_credential(class_id: str, provider_id: str):
        access_error = _require_class_admin_access(class_id)
        if access_error:
            return access_error
        service, service_error = _get_ai_credential_service(
            get_db(),
            credential_service_provider,
        )
        if service_error:
            return service_error
        try:
            deleted = service.delete_class_credential(class_id, provider_id)
        except ValueError as exc:
            return _error("VALIDATION_ERROR", str(exc), 422)
        if not deleted:
            return _error("NOT_FOUND", "AI credential was not found.", 404)
        return jsonify({
            "data": {
                "class_id": class_id,
                "provider_id": provider_id,
                "status": "deleted",
            }
        }), 200

    @blueprint.patch("/classes/<class_id>/ai/settings")
    def update_class_ai_settings(class_id: str):
        access_error = _require_class_admin_access(class_id)
        if access_error:
            return access_error
        db = get_db()
        if not db:
            return _error("FIREBASE_UNAVAILABLE", "Firebase is not connected.", 503)
        payload, error = _json_body()
        if error:
            return error
        settings, error = _validate_ai_settings(payload)
        if error:
            return error
        settings.update({
            "updated_at": _now_iso(),
            "updated_by": g.dashboard_principal.admin_id,
        })
        _ai_settings_ref(db, class_id).set(settings, merge=True)
        return jsonify({"data": _get_ai_settings(db, class_id)}), 200

    return blueprint


def _dashboard_principal_from_headers() -> DashboardPrincipal:
    admin_id = request.headers.get("X-MTC-Admin-Id", "").strip()
    role = request.headers.get("X-MTC-Admin-Role", "").strip()
    class_ids = frozenset(
        value.strip()
        for value in request.headers.get("X-MTC-Admin-Classes", "").split(",")
        if value.strip()
    )
    authenticated = bool(admin_id and role in {"super_admin", "class_admin"})
    return DashboardPrincipal(admin_id, role, class_ids, authenticated)


def _require_class_admin_access(class_id: str):
    if not _env_flag("ALLOW_CLASS_BYOK", default=True):
        return _error(
            "CLASS_BYOK_DISABLED",
            "Class AI credentials are disabled.",
            503,
        )
    if not is_valid_class_id(class_id):
        return _error("VALIDATION_ERROR", "class_id is invalid.", 422)
    principal = getattr(g, "dashboard_principal", None)
    if not principal or not principal.authenticated:
        return _error(
            "ADMIN_PRINCIPAL_REQUIRED",
            "Authenticated dashboard principal claims are required.",
            403,
        )
    if principal.role == "super_admin":
        return None
    return _error(
        "SUPER_ADMIN_REQUIRED",
        "BYOK v1 is managed by super admins only.",
        403,
    )


def _env_flag(name: str, *, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _default_ai_credential_service(db) -> AICredentialService:
    return AICredentialService(
        db,
        build_credential_cipher_from_env(),
        system_credentials=system_credentials_from_env(),
    )


def _get_ai_credential_service(db, provider: CredentialServiceProvider):
    if not db:
        return None, _error("FIREBASE_UNAVAILABLE", "Firebase is not connected.", 503)
    try:
        return provider(db), None
    except (ValueError, TypeError) as exc:
        logger.warning("AI credential service is unavailable: %s", exc)
        return None, _error(
            "AI_CREDENTIALS_NOT_CONFIGURED",
            "AI credential encryption is not configured.",
            503,
        )


def _validate_credential_payload(provider_id: str, payload: Dict[str, Any]):
    try:
        definition = get_provider_definition(provider_id)
    except ValueError as exc:
        return "", "", _error("VALIDATION_ERROR", str(exc), 422)

    unknown_keys = sorted(set(payload) - {"api_key", "model"})
    if unknown_keys:
        return "", "", _error(
            "VALIDATION_ERROR",
            f"Unknown credential fields: {', '.join(unknown_keys)}.",
            422,
        )
    api_key = payload.get("api_key")
    model = payload.get("model")
    if not isinstance(api_key, str) or not api_key.strip():
        return "", "", _error("VALIDATION_ERROR", "api_key is required.", 422)
    if len(api_key.strip()) > 500:
        return "", "", _error(
            "VALIDATION_ERROR",
            "api_key must be 500 characters or fewer.",
            422,
        )
    if not isinstance(model, str):
        return "", "", _error("VALIDATION_ERROR", "model is required.", 422)
    try:
        definition.validate_model(model.strip())
    except ValueError as exc:
        return "", "", _error("VALIDATION_ERROR", str(exc), 422)
    return api_key.strip(), model.strip(), None


def _validate_ai_settings(payload: Dict[str, Any]):
    allowed = {
        "selected_provider",
        "selected_model",
        "system_fallback_enabled",
        "daily_fallback_request_budget",
        "daily_fallback_token_budget",
    }
    unknown_keys = sorted(set(payload) - allowed)
    if unknown_keys:
        return {}, _error(
            "VALIDATION_ERROR",
            f"Unknown AI settings fields: {', '.join(unknown_keys)}.",
            422,
        )
    provider_id = payload.get("selected_provider")
    model = payload.get("selected_model")
    if not isinstance(provider_id, str) or not isinstance(model, str):
        return {}, _error(
            "VALIDATION_ERROR",
            "selected_provider and selected_model are required.",
            422,
        )
    try:
        definition = get_provider_definition(provider_id.strip())
        definition.validate_model(model.strip())
    except ValueError as exc:
        return {}, _error("VALIDATION_ERROR", str(exc), 422)

    fallback_enabled = payload.get("system_fallback_enabled")
    if not isinstance(fallback_enabled, bool):
        return {}, _error(
            "VALIDATION_ERROR",
            "system_fallback_enabled must be a boolean.",
            422,
        )
    request_budget = _validated_budget(
        payload.get("daily_fallback_request_budget"),
        "daily_fallback_request_budget",
        maximum=1000,
    )
    if isinstance(request_budget, tuple):
        return {}, request_budget
    token_budget = _validated_budget(
        payload.get("daily_fallback_token_budget"),
        "daily_fallback_token_budget",
        maximum=10_000_000,
    )
    if isinstance(token_budget, tuple):
        return {}, token_budget

    return {
        "selected_provider": provider_id.strip(),
        "selected_model": model.strip(),
        "system_fallback_enabled": fallback_enabled,
        "daily_fallback_request_budget": request_budget,
        "daily_fallback_token_budget": token_budget,
    }, None


def _validated_budget(value, field_name: str, maximum: int):
    if isinstance(value, bool) or not isinstance(value, int):
        return _error("VALIDATION_ERROR", f"{field_name} must be an integer.", 422)
    if value < 0 or value > maximum:
        return _error(
            "VALIDATION_ERROR",
            f"{field_name} must be between 0 and {maximum}.",
            422,
        )
    return value


def _ai_settings_ref(db, class_id: str):
    return (
        db.collection("classes")
        .document(class_id)
        .collection("config")
        .document("ai")
    )


def _get_ai_settings(db, class_id: str) -> Dict[str, Any]:
    snapshot = _ai_settings_ref(db, class_id).get()
    data = snapshot.to_dict() if getattr(snapshot, "exists", False) else {}
    provider_id = str(data.get("selected_provider") or "gemini")
    try:
        definition = get_provider_definition(provider_id)
    except ValueError:
        definition = get_provider_definition("gemini")
    model = str(data.get("selected_model") or definition.default_model)
    try:
        definition.validate_model(model)
    except ValueError:
        model = definition.default_model
    return {
        "class_id": class_id,
        "selected_provider": definition.provider_id,
        "selected_model": model,
        "system_fallback_enabled": bool(data.get("system_fallback_enabled", True)),
        "daily_fallback_request_budget": int(
            data.get("daily_fallback_request_budget", 20) or 0
        ),
        "daily_fallback_token_budget": int(
            data.get("daily_fallback_token_budget", 30000) or 0
        ),
        "updated_at": _json_safe(data.get("updated_at")),
        "updated_by": str(data.get("updated_by") or ""),
    }


def _error(code: str, message: str, status: int):
    return jsonify({
        "error": {
            "code": code,
            "message": message,
            "request_id": request.headers.get("X-Request-ID", ""),
        }
    }), status


def _json_body() -> Tuple[Dict[str, Any], Optional[Any]]:
    if not request.is_json:
        return {}, _error("INVALID_JSON", "Request body must be JSON.", 400)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return {}, _error("INVALID_JSON", "Request body must be a JSON object.", 400)
    return payload, None


def _validate_links_target(db, class_id: str, term_id: str):
    if not db:
        return _error("FIREBASE_UNAVAILABLE", "Firebase is not connected.", 503)
    if not is_valid_class_id(class_id):
        return _error("VALIDATION_ERROR", "class_id is invalid.", 422)
    if not TERM_ID_PATTERN.fullmatch(term_id or ""):
        return _error("VALIDATION_ERROR", "term_id is invalid.", 422)

    registry = get_class_registry_entry(db, class_id)
    if not registry:
        return _error("NOT_FOUND", "Class registry entry was not found.", 404)
    if registry.active_term_id != term_id:
        return _error("VALIDATION_ERROR", "Only the active term can be edited.", 422)

    term_doc = (
        db.collection("classes")
        .document(class_id)
        .collection("terms")
        .document(term_id)
        .collection("metadata")
        .document("main")
        .get()
    )
    if not getattr(term_doc, "exists", False):
        return _error("NOT_FOUND", "Term metadata was not found.", 404)
    return None


def _links_doc_ref(db, class_id: str, term_id: str):
    return (
        db.collection("classes")
        .document(class_id)
        .collection("terms")
        .document(term_id)
        .collection("config")
        .document("links")
    )


def _validate_links_payload(payload: Dict[str, Any]) -> Tuple[Dict[str, str], Optional[Any]]:
    unknown_keys = sorted(set(payload) - set(LINK_KEYS))
    if unknown_keys:
        return {}, _error("VALIDATION_ERROR", f"Unknown link fields: {', '.join(unknown_keys)}.", 422)

    links: Dict[str, str] = {}
    for key in LINK_KEYS:
        value = payload.get(key, "")
        if not isinstance(value, str):
            return {}, _error("VALIDATION_ERROR", f"{key} must be a string.", 422)
        value = value.strip()
        invalid_reason = _invalid_link_value(value)
        if invalid_reason:
            return {}, _error("VALIDATION_ERROR", f"{key} {invalid_reason}.", 422)
        links[key] = value
    return links, None


def _invalid_link_value(value: str) -> str | None:
    if not value:
        return None
    if LOCAL_PATH_PATTERN.match(value) or "\\" in value:
        return "must not be a local or relative path"
    if value.startswith(("http://", "file://")):
        return "must use https://"
    if not value.startswith("https://"):
        return "must use https://"
    if SECRET_VALUE_PATTERN.search(value):
        return "must not contain secret-looking values"
    return None


def _extract_links(data: Dict[str, Any]) -> Dict[str, str]:
    return {
        key: str(data.get(key) or "").strip()
        for key in LINK_KEYS
    }


def _links_response(class_id: str, term_id: str, links: Dict[str, str], data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "class_id": class_id,
        "term_id": term_id,
        "links": links,
        "effective_links": merge_link_values(get_safe_fallback_links(include_worksheet=False), links),
        "updated_at": _json_safe(data.get("updated_at")),
        "updated_by": str(data.get("updated_by") or ""),
    }


def _image_body() -> Tuple[bytes, str, Optional[Any]]:
    if request.files:
        file = request.files.get("image")
        if not file:
            return b"", "", _error("VALIDATION_ERROR", "image file is required.", 422)
        image_bytes = file.stream.read(MAX_IMAGE_BYTES + 1)
        return _validate_image_payload(image_bytes, file.mimetype or "application/octet-stream")

    payload, error = _json_body()
    if error:
        return b"", "", error
    image_base64 = str(payload.get("image_base64", "")).strip()
    mime_type = str(payload.get("mime_type", "image/jpeg")).strip() or "image/jpeg"
    if not image_base64:
        return b"", "", _error("VALIDATION_ERROR", "image_base64 is required.", 422)
    if "," in image_base64 and image_base64.lower().startswith("data:"):
        header, image_base64 = image_base64.split(",", 1)
        if ";" in header:
            mime_type = header[5:].split(";", 1)[0] or mime_type
    if len(image_base64) > _max_base64_length():
        return b"", "", _error("VALIDATION_ERROR", "Image is larger than 6 MB.", 422)
    try:
        image_bytes = base64.b64decode(image_base64, validate=True)
    except (binascii.Error, ValueError):
        return b"", "", _error("VALIDATION_ERROR", "image_base64 is invalid.", 422)
    return _validate_image_payload(image_bytes, mime_type)


def _max_base64_length() -> int:
    return ((MAX_IMAGE_BYTES + 2) // 3) * 4


def _validate_image_payload(image_bytes: bytes, declared_mime: str) -> Tuple[bytes, str, Optional[Any]]:
    mime_type = (declared_mime or "application/octet-stream").split(";", 1)[0].strip().lower()
    if not image_bytes:
        return b"", "", _error("VALIDATION_ERROR", "Image content is empty.", 422)
    if len(image_bytes) > MAX_IMAGE_BYTES:
        return b"", "", _error("VALIDATION_ERROR", "Image is larger than 6 MB.", 422)
    if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        return b"", "", _error("VALIDATION_ERROR", "Only JPEG, PNG, and WebP images are supported.", 422)

    detected_mime = _detect_image_mime(image_bytes)
    if detected_mime is None:
        return b"", "", _error("VALIDATION_ERROR", "Image file signature is invalid.", 422)
    if detected_mime != mime_type:
        return b"", "", _error("VALIDATION_ERROR", "Image MIME type does not match its file signature.", 422)
    return image_bytes, mime_type, None


def _detect_image_mime(image_bytes: bytes) -> Optional[str]:
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(image_bytes) >= 12 and image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return None


def _pagination(default_limit: int, max_limit: int) -> Tuple[int, int]:
    try:
        limit = int(request.args.get("limit", default_limit))
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError):
        return default_limit, 0
    limit = max(1, min(limit, max_limit))
    offset = max(0, offset)
    return limit, offset


def _build_sustainability_impact(db, metrics: Dict[str, Any]) -> Dict[str, Any]:
    active_students = broadcast.get_user_count() if db else 0
    homework_count = _count_collection(db, "homeworks")
    broadcast_count, broadcast_recipients = _broadcast_totals(db)
    automated_request_count = int(metrics.get("total_requests", 0) or 0)

    paper_saved_sheets = (homework_count + broadcast_count) * active_students
    admin_minutes_saved = (
        automated_request_count * 1.0
        + homework_count * 3.0
        + broadcast_count * max(active_students - 1, 0) * 0.5
    )
    equal_access_rate = 0.0
    if MTC_EXPECTED_CLASS_SIZE > 0:
        equal_access_rate = min(100.0, (active_students / MTC_EXPECTED_CLASS_SIZE) * 100)

    return {
        "active_students": active_students,
        "expected_class_size": MTC_EXPECTED_CLASS_SIZE,
        "homework_count": homework_count,
        "broadcast_count": broadcast_count,
        "broadcast_recipients": broadcast_recipients,
        "automated_request_count": automated_request_count,
        "paper_saved_sheets": int(paper_saved_sheets),
        "admin_minutes_saved": round(admin_minutes_saved, 1),
        "admin_hours_saved": round(admin_minutes_saved / 60, 2),
        "co2_saved_grams": round(paper_saved_sheets * PAPER_CO2_GRAMS_PER_SHEET, 1),
        "equal_access_rate_percent": round(equal_access_rate, 1),
        "assumptions": {
            "paper_factor": "1 sheet per homework or broadcast per active student",
            "standard_command_minutes_saved": 1.0,
            "homework_entry_minutes_saved": 3.0,
            "broadcast_resend_minutes_saved_per_student": 0.5,
            "co2_grams_per_sheet": PAPER_CO2_GRAMS_PER_SHEET,
        },
    }


def _count_collection(db, collection_name: str) -> int:
    if not db:
        return 0
    try:
        return sum(1 for _ in db.collection(collection_name).stream())
    except Exception as e:
        logger.warning("Could not count %s: %s", collection_name, e)
        return 0


def _broadcast_totals(db) -> Tuple[int, int]:
    if not db:
        return 0, 0
    try:
        total = 0
        recipients = 0
        for doc in db.collection("broadcast_history").stream():
            data = doc.to_dict() or {}
            total += 1
            recipients += int(data.get("sent_count", 0) or 0)
        return total, recipients
    except Exception as e:
        logger.warning("Could not count broadcast history: %s", e)
        return 0, 0


def _serialize_doc(doc) -> Dict[str, Any]:
    data = doc.to_dict() or {}
    data["id"] = doc.id
    return {key: _json_safe(value) for key, value in data.items()}


def _json_safe(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


def _get_recent_homeworks(db, limit: int) -> list:
    if not db:
        return []
    try:
        docs = db.collection("homeworks").order_by(
            "created_at",
            direction=firestore.Query.DESCENDING,
        ).limit(limit).stream()
        return [_serialize_doc(doc) for doc in docs]
    except Exception as e:
        logger.error("Dashboard homework query failed: %s", e)
        return []


def _get_recent_broadcasts(db, limit: int) -> list:
    if not db:
        return []
    try:
        docs = db.collection("broadcast_history").order_by(
            "timestamp",
            direction=firestore.Query.DESCENDING,
        ).limit(limit).stream()
        return [_serialize_doc(doc) for doc in docs]
    except Exception as e:
        logger.error("Dashboard broadcast query failed: %s", e)
        return []


def _now_iso() -> str:
    return datetime.datetime.now(tz=LOCAL_TZ).isoformat()
