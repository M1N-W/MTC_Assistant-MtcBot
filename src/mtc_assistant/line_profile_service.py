# -*- coding: utf-8 -*-
"""Cached LINE profile synchronization."""

from __future__ import annotations

import datetime
from urllib.parse import urlparse

from mtc_assistant.config import LOCAL_TZ, logger


PROFILE_FRESHNESS_HOURS = 24


def sync_line_profile_if_stale(db, user_id: str, line_api, *, now_provider=None) -> bool:
    if not db or not user_id or not line_api:
        return False
    now_provider = now_provider or (lambda: datetime.datetime.now(tz=LOCAL_TZ))
    user_ref = db.collection("users").document(user_id)
    try:
        snapshot = user_ref.get()
        data = snapshot.to_dict() if getattr(snapshot, "exists", False) else {}
        if _is_fresh(data.get("profile_synced_at"), now_provider()):
            return False
        profile = line_api.get_profile(user_id)
        payload = {
            "line_display_name": str(getattr(profile, "display_name", "") or "").strip(),
            "profile_synced_at": now_provider().isoformat(),
        }
        picture_url = str(getattr(profile, "picture_url", "") or "").strip()
        if _is_https_url(picture_url):
            payload["line_picture_url"] = picture_url
        user_ref.set(payload, merge=True)
        return True
    except Exception as exc:
        logger.warning("LINE profile sync failed for user: %s", exc)
        return False


def _is_https_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _is_fresh(value, now: datetime.datetime) -> bool:
    if not value:
        return False
    try:
        synced_at = datetime.datetime.fromisoformat(str(value))
    except ValueError:
        return False
    if synced_at.tzinfo is None:
        synced_at = synced_at.replace(tzinfo=LOCAL_TZ)
    return now - synced_at < datetime.timedelta(hours=PROFILE_FRESHNESS_HOURS)
