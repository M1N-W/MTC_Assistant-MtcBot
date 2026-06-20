# -*- coding: utf-8 -*-
"""CLI utility to issue MTC teacher verification codes securely."""

from __future__ import annotations

import argparse
import base64
import datetime
import json
import os
import re
import secrets
import sys

from mtc_assistant.config import FIREBASE_KEY_PATH, LOCAL_TZ
from mtc_assistant.dashboard_auth_models import hash_password


def connect_firestore():
    import firebase_admin
    from firebase_admin import credentials, firestore

    raw = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if raw:
        return firestore.client() if firebase_admin._apps else firebase_admin.initialize_app(credentials.Certificate(json.loads(raw))).client()

    b64 = os.environ.get("FIREBASE_CREDENTIALS_BASE64")
    if b64:
        decoded = base64.b64decode(b64).decode("utf-8")
        return firestore.client() if firebase_admin._apps else firebase_admin.initialize_app(credentials.Certificate(json.loads(decoded))).client()

    # Fallback to key path on disk (relative to project parent directory)
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    key_path = os.path.join(root, FIREBASE_KEY_PATH)
    if os.path.exists(key_path):
        return firestore.client() if firebase_admin._apps else firebase_admin.initialize_app(credentials.Certificate(key_path)).client()

    raise RuntimeError("No Firebase credentials found.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Issue MTC teacher verification code.")
    parser.add_argument("--teacher-id", required=True, help="Target teacher ID.")
    parser.add_argument("--expires-in-hours", type=int, default=24, help="Expiry in hours (1-168).")
    parser.add_argument("--max-attempts", type=int, default=5, help="Maximum attempts (1-10).")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry-run check.")
    parser.add_argument("--apply", action="store_true", help="Apply changes to Firestore.")

    args = parser.parse_args(argv)

    if args.dry_run and args.apply:
        print("Error: --dry-run and --apply are mutually exclusive.", file=sys.stderr)
        return 1

    is_dry_run = args.dry_run or not args.apply

    teacher_id = str(args.teacher_id or "").strip()
    if not re.match(r"^[a-zA-Z0-9_-]{3,64}$", teacher_id):
        print("Error: Invalid teacher_id format.", file=sys.stderr)
        return 1

    if not (1 <= args.expires_in_hours <= 168):
        print("Error: expires-in-hours must be between 1 and 168.", file=sys.stderr)
        return 1

    if not (1 <= args.max_attempts <= 10):
        print("Error: max-attempts must be between 1 and 10.", file=sys.stderr)
        return 1

    try:
        db = connect_firestore()
    except Exception:
        print("Error: Firestore is unavailable.", file=sys.stderr)
        return 1

    teacher_ref = db.collection("system").document("teacher_directory").collection("records").document(teacher_id)
    try:
        teacher_doc = teacher_ref.get()
    except Exception:
        print("Error: Firestore is unavailable.", file=sys.stderr)
        return 1

    if not getattr(teacher_doc, "exists", False):
        print("Error: Teacher record does not exist.", file=sys.stderr)
        return 1

    teacher_data = teacher_doc.to_dict() or {}
    if teacher_data.get("status", "active") != "active":
        print("Error: Teacher is not active.", file=sys.stderr)
        return 1

    verification_ref = db.collection("system").document("teacher_verification").collection("records").document(teacher_id)
    try:
        verification_doc = verification_ref.get()
    except Exception:
        print("Error: Firestore is unavailable.", file=sys.stderr)
        return 1

    existing_replaced = getattr(verification_doc, "exists", False)

    if is_dry_run:
        result = {
            "dry_run": True,
            "teacher_id": teacher_id,
            "teacher_record_exists": True,
            "teacher_status": "active",
            "existing_credential_replaced": existing_replaced,
            "expires_in_hours": args.expires_in_hours,
            "max_attempts": args.max_attempts,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    # Generation and application logic
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    code = "".join(secrets.choice(alphabet) for _ in range(16))

    try:
        code_hash = hash_password(code, teacher_id)
    except Exception as exc:
        print(f"Error: Code hashing failed: {exc}", file=sys.stderr)
        return 1

    now = datetime.datetime.now(LOCAL_TZ)
    expires_at = now + datetime.timedelta(hours=args.expires_in_hours)

    verification_data = {
        "teacher_id": teacher_id,
        "verification_code_hash": code_hash,
        "status": "active",
        "failed_attempts": 0,
        "max_attempts": args.max_attempts,
        "expires_at": expires_at.isoformat(),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "used_at": None,
        "issued_by": "local_operator",
    }

    try:
        verification_ref.set(verification_data)
    except Exception:
        print("Error: Firestore write failed.", file=sys.stderr)
        return 1

    # Output the plaintext code exactly once to stdout
    print("SUCCESS: Teacher verification code generated and applied to Firestore.")
    print("Deliver the following code privately to the intended teacher:")
    print(f"Code: {code}")
    print("This code will NOT be shown again. It must be delivered privately.")
    print(f"Expires at: {expires_at.isoformat()}")
    return 0
