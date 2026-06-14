"""Controlled CLI for creating the first dashboard super administrator."""

from __future__ import annotations

import argparse
import datetime
import getpass
import hashlib
import json
import sys
import uuid
from typing import Any, Callable, TextIO

from mtc_assistant.dashboard_auth_models import Account, hash_password, normalize_username
from mtc_assistant.dashboard_auth_repository import FirestoreDashboardAuthRepository
from mtc_assistant.dashboard_security_audit import SecurityAuditEvent


def bootstrap_super_admin(
    repository: Any,
    *,
    username: str,
    password: str,
    now: datetime.datetime | None = None,
) -> Account:
    timestamp = now or datetime.datetime.now(datetime.timezone.utc)
    normalized = normalize_username(username)
    account = Account.create(
        uuid.uuid4().hex,
        normalized,
        hash_password(password, normalized),
        "super_admin",
        [],
        now=timestamp,
        created_by="bootstrap_cli",
    )
    audit = SecurityAuditEvent.create(
        "super_admin_bootstrap",
        timestamp,
        actor_account_id="bootstrap_cli",
        target_account_id=account.account_id,
    )
    repository.bootstrap_super_admin(
        account,
        hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        audit,
    )
    return account


def main(
    argv: list[str] | None = None,
    *,
    repository_factory: Callable[[], Any] | None = None,
    input_fn: Callable[[str], str] = input,
    getpass_fn: Callable[[str], str] = getpass.getpass,
    stdout: TextIO = sys.stdout,
) -> int:
    parser = argparse.ArgumentParser(
        description="Create the first Flask-owned dashboard super administrator."
    )
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--username", required=True)
    args = parser.parse_args(argv)

    try:
        repository = (repository_factory or _repository)()
        actual_project_id = repository.project_id()
        if args.project_id != actual_project_id:
            raise ValueError("Configured Firebase project ID does not match --project-id.")
        confirmation = input_fn(
            f"Type Firebase project ID '{actual_project_id}' to confirm: "
        )
        if confirmation != actual_project_id:
            raise ValueError("Firebase project ID confirmation did not match.")
        password = getpass_fn("Password: ")
        password_confirmation = getpass_fn("Confirm password: ")
        if password != password_confirmation:
            raise ValueError("Password confirmation did not match.")
        account = bootstrap_super_admin(
            repository,
            username=args.username,
            password=password,
        )
    except (RuntimeError, ValueError) as exc:
        json.dump({"status": "refused", "message": str(exc)}, stdout)
        stdout.write("\n")
        return 2

    json.dump(
        {
            "status": "created",
            "project_id": actual_project_id,
            "account_id": account.account_id,
        },
        stdout,
    )
    stdout.write("\n")
    return 0


def _repository() -> FirestoreDashboardAuthRepository:
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError as exc:
        raise RuntimeError("firebase-admin is required for bootstrap") from exc
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.ApplicationDefault())
    client = firestore.client()
    return FirestoreDashboardAuthRepository(lambda: client)


if __name__ == "__main__":
    raise SystemExit(main())
