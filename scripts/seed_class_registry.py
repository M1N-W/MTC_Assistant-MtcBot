#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Seed class registry foundation documents for MTC Assistant.

Default mode is dry-run. Pass --apply to write to Firestore.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from mtc_assistant.config import (  # noqa: E402
    ABSENCE_LINK,
    FIREBASE_KEY_PATH,
    GRADE_LINK,
    LOCAL_TZ,
    SCHOOL_LINK,
    SCHEDULE,
    WORKSHEET_LINK,
)
from mtc_assistant.invite_codes import is_valid_class_id, is_valid_invite_code  # noqa: E402
from mtc_assistant.links_service import (  # noqa: E402
    ABSENCE_FORM_URL,
    GRADE_URL,
    SCHOOL_URL,
    WORKSHEET_URL,
)
from mtc_assistant.timetable_service import build_timetable_config  # noqa: E402


DEFAULT_TERM_ID = "2569-t1"
MTC11_SCHEDULE = {
    0: [
        {"period": 1, "start": "08:30", "end": "09:25", "subject": "จ33207 · ครูไพลิน", "room": "634"},
        {"period": 2, "start": "09:25", "end": "10:20", "subject": "ค33101 · ครูทักษิณ", "room": "634"},
        {"period": 3, "start": "10:20", "end": "11:15", "subject": "ค33201 · ครูสุนิสา", "room": "634"},
        {"period": 4, "start": "11:15", "end": "12:10", "subject": "ว30225 · ครูวรรณี", "room": "313"},
        {"period": 5, "start": "12:10", "end": "13:05", "subject": "พัก", "room": "-"},
        {"period": 6, "start": "13:05", "end": "14:00", "subject": "ว30205 · ครูจิราภรณ์", "room": "335"},
        {"period": 7, "start": "14:00", "end": "14:55", "subject": "ว30205 · ครูจิราภรณ์", "room": "335"},
        {"period": 8, "start": "14:55", "end": "15:50", "subject": "ท33101 · ครูวาทิยา", "room": "634"},
    ],
    1: [
        {"period": 1, "start": "08:30", "end": "09:25", "subject": "ค33201 · ครูสุนิสา", "room": "634"},
        {"period": 2, "start": "09:25", "end": "10:20", "subject": "ว30161 · ครูพัชราภรณ์", "room": "329"},
        {"period": 3, "start": "10:20", "end": "11:15", "subject": "ว30161 · ครูพัชราภรณ์", "room": "329"},
        {"period": 4, "start": "11:15", "end": "12:10", "subject": "ส33101 · ครูพงศ์พิชิต", "room": "634"},
        {"period": 5, "start": "12:10", "end": "13:05", "subject": "พัก", "room": "-"},
        {"period": 6, "start": "13:05", "end": "14:00", "subject": "อ33101 · ครูพัชรี(พ)", "room": "634"},
        {"period": 7, "start": "14:00", "end": "14:55", "subject": "อ33207 · T3/พัชรี", "room": "634"},
        {"period": 8, "start": "14:55", "end": "15:50", "subject": "ว30245 · ครูปาณิศา", "room": "323"},
    ],
    2: [
        {"period": 1, "start": "08:30", "end": "09:25", "subject": "ว30245 · ครูปาณิศา", "room": "323"},
        {"period": 2, "start": "09:25", "end": "10:20", "subject": "ว30245 · ครูปาณิศา", "room": "323"},
        {"period": 3, "start": "10:20", "end": "11:15", "subject": "ค33201 · ครูสุนิสา", "room": "634"},
        {"period": 4, "start": "11:15", "end": "12:10", "subject": "แนะแนว · ครูสมฤทัย", "room": "634"},
        {"period": 5, "start": "12:10", "end": "13:05", "subject": "พัก", "room": "-"},
        {"period": 6, "start": "13:05", "end": "14:00", "subject": "อ33101 · พัชรี*", "room": "634"},
        {"period": 7, "start": "14:00", "end": "14:55", "subject": "โฮมรูม/ประชุม ม.6", "room": "-"},
        {"period": 8, "start": "14:55", "end": "15:50", "subject": "กิจกรรม", "room": "-"},
    ],
    3: [
        {"period": 1, "start": "08:30", "end": "09:25", "subject": "ว30225 · ครูวรรณี", "room": "313"},
        {"period": 2, "start": "09:25", "end": "10:20", "subject": "ว30225 · ครูวรรณี", "room": "313"},
        {"period": 3, "start": "10:20", "end": "11:15", "subject": "จ33207 · ครูไพลิน", "room": "634"},
        {"period": 4, "start": "11:15", "end": "12:10", "subject": "ค33201 · ครูสุนิสา", "room": "634"},
        {"period": 5, "start": "12:10", "end": "13:05", "subject": "พัก", "room": "-"},
        {"period": 6, "start": "13:05", "end": "14:00", "subject": "ว30205 · ครูจิราภรณ์", "room": "634"},
        {"period": 7, "start": "14:00", "end": "14:55", "subject": "ว30205 · ครูจิราภรณ์", "room": "634"},
        {"period": 8, "start": "14:55", "end": "15:50", "subject": "ค33203 · ครูชลิต", "room": "634"},
        {"period": 9, "start": "15:50", "end": "16:45", "subject": "ค33203 · ครูชลิต", "room": "634"},
    ],
    4: [
        {"period": 1, "start": "08:30", "end": "09:25", "subject": "ค33101 · ครูทักษิณ", "room": "634"},
        {"period": 2, "start": "09:25", "end": "10:20", "subject": "ส33101 · ครูพงศ์พิชิต", "room": "634"},
        {"period": 3, "start": "10:20", "end": "11:15", "subject": "อ33101 · ครูพัชรี(พ)", "room": "634"},
        {"period": 4, "start": "11:15", "end": "12:10", "subject": "ท33101 · ครูวาทิยา", "room": "634"},
        {"period": 5, "start": "12:10", "end": "13:05", "subject": "พัก", "room": "-"},
        {"period": 6, "start": "13:05", "end": "14:00", "subject": "ศ33101 · ครูอภิรดี", "room": "411"},
        {"period": 7, "start": "14:00", "end": "14:55", "subject": "ว30161 · ครูพัชราภรณ์", "room": "329"},
        {"period": 8, "start": "14:55", "end": "15:50", "subject": "พ33101 · ครูประกิต", "room": "โดม2"},
    ],
}
MTC13_SCHEDULE = {
    0: [
        {"start": "08:30", "end": "09:25", "subject": "คอมพิวเตอร์ (ครูจินดาพร)", "room": "221"},
        {"start": "09:25", "end": "10:20", "subject": "คอมพิวเตอร์ (ครูจินดาพร)", "room": "221"},
        {"start": "10:20", "end": "11:15", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "331"},
        {"start": "11:15", "end": "12:10", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "331"},
        {"start": "13:05", "end": "14:00", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "632"},
        {"start": "14:00", "end": "14:55", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "632"},
        {"start": "14:55", "end": "15:50", "subject": "สุข&พละ (ครูนรเศรษฐ์)", "room": "โดม3"},
        {"start": "15:50", "end": "16:45", "subject": "คณิตเพิ่มพูน (ครูวรัญญา)", "room": "632"},
    ],
    1: [
        {"start": "08:30", "end": "09:25", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "331"},
        {"start": "09:25", "end": "10:20", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "331"},
        {"start": "10:20", "end": "11:15", "subject": "ภาษาไทย (ครูเบญจมาศ)", "room": "632"},
        {"start": "11:15", "end": "12:10", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "632"},
        {"start": "13:05", "end": "14:00", "subject": "อังกฤษเพิ่มเติม (Teacher)", "room": "632"},
        {"start": "14:00", "end": "14:55", "subject": "สังคมศึกษา (ครูบังอร)", "room": "632"},
        {"start": "14:55", "end": "15:50", "subject": "IS (ครูปรียา)", "room": "632"},
        {"start": "15:50", "end": "16:45", "subject": "IS (ครูปรียา)", "room": "632"},
    ],
    2: [
        {"start": "08:30", "end": "09:25", "subject": "ชีววิทยา (ครูพิชามญช์)", "room": "321"},
        {"start": "09:25", "end": "10:20", "subject": "ชีววิทยา (ครูพิชามญช์)", "room": "321"},
        {"start": "10:20", "end": "11:15", "subject": "อังกฤษพื้นฐาน (ครูนพรัตน์)", "room": "632"},
        {"start": "11:15", "end": "12:10", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "632"},
        {"start": "13:05", "end": "14:00", "subject": "โฮมรูม/ประชุม ม.4", "room": "-"},
        {"start": "14:00", "end": "14:55", "subject": "หน้าที่ฯ (ครูมานพ)", "room": "632"},
        {"start": "14:55", "end": "15:50", "subject": "กิจกรรม", "room": "-"},
    ],
    3: [
        {"start": "08:30", "end": "09:25", "subject": "อังกฤษพื้นฐาน (ครูนพรัตน์)", "room": "632"},
        {"start": "09:25", "end": "10:20", "subject": "สังคมศึกษา (ครูบังอร)", "room": "632"},
        {"start": "10:20", "end": "11:15", "subject": "คณิตพื้นฐาน (ครูปรียา)", "room": "632"},
        {"start": "11:15", "end": "12:10", "subject": "เคมี (ครูกัลยา)", "room": "313"},
        {"start": "13:05", "end": "14:00", "subject": "นาฏศิลป์ (ครูบังเอิญ)", "room": "575"},
        {"start": "14:00", "end": "14:55", "subject": "แนะแนว (ครูทศพร)", "room": "632"},
        {"start": "14:55", "end": "15:50", "subject": "คณิตศาสตร์ (ครูมานพ)", "room": "632"},
        {"start": "15:50", "end": "16:45", "subject": "คณิตศาสตร์ (ครูมานพ)", "room": "632"},
    ],
    4: [
        {"start": "08:30", "end": "09:25", "subject": "คณิตพื้นฐาน (ครูปรียา)", "room": "632"},
        {"start": "09:25", "end": "10:20", "subject": "อังกฤษเพิ่มเติม (Teacher)", "room": "632"},
        {"start": "10:20", "end": "11:15", "subject": "เคมี (ครูกัลยา)", "room": "313"},
        {"start": "11:15", "end": "12:10", "subject": "เคมี (ครูกัลยา)", "room": "313"},
        {"start": "13:05", "end": "14:00", "subject": "ภาษาไทย (ครูเบญจมาศ)", "room": "632"},
        {"start": "14:00", "end": "14:55", "subject": "ประวัติศาสตร์ (ครูณฐพร)", "room": "632"},
        {"start": "14:55", "end": "15:50", "subject": "ชีววิทยา (ครูพิชามญช์)", "room": "321"},
    ],
}
TIMETABLE_SEEDS = {
    "mtc11": MTC11_SCHEDULE,
    "mtc12": SCHEDULE,
    "mtc13": MTC13_SCHEDULE,
}
TIMETABLE_IMAGE_URLS = {
    "mtc11": "https://img2.pic.in.th/290922.jpg",
    "mtc12": "https://img2.pic.in.th/186308.jpg",
    "mtc13": "https://img2.pic.in.th/SaveClip.App_702397967_18144615751449592_1572400629043110676_n.jpg",
}
LINK_SEEDS = {
    "mtc12": {
        WORKSHEET_URL: WORKSHEET_LINK,
        SCHOOL_URL: SCHOOL_LINK,
        GRADE_URL: GRADE_LINK,
        ABSENCE_FORM_URL: ABSENCE_LINK,
    },
    "mtc13": {
        SCHOOL_URL: SCHOOL_LINK,
        GRADE_URL: GRADE_LINK,
        ABSENCE_FORM_URL: ABSENCE_LINK,
    },
}
CLASS_SEEDS = {
    "mtc11": {
        "display_name": "MTC11",
        "status": "active",
        "active_term_id": DEFAULT_TERM_ID,
        "grade_level": "m6",
        "room_label": "ม.6/2",
        "homeroom_room": "634",
        "term_display_name": "ภาคเรียนที่ 1/2569",
    },
    "mtc12": {
        "display_name": "MTC12",
        "status": "active",
        "active_term_id": DEFAULT_TERM_ID,
        "grade_level": "m5",
        "room_label": "ม.5/2",
    },
    "mtc13": {
        "display_name": "MTC13",
        "status": "active",
        "active_term_id": DEFAULT_TERM_ID,
        "grade_level": "m4",
        "room_label": "ม.4/2",
    },
}


@dataclass(frozen=True)
class SeedOperation:
    path: str
    data: dict[str, Any]
    merge: bool = True


def build_seed_operations(invite_args: list[str] | None = None) -> list[SeedOperation]:
    now = datetime.datetime.now(tz=LOCAL_TZ).isoformat()
    operations: list[SeedOperation] = []

    for class_id, seed in CLASS_SEEDS.items():
        registry_data = {
            **seed,
            "class_id": class_id,
            "updated_at": now,
        }
        class_metadata = {
            "display_name": seed["display_name"],
            "status": seed["status"],
            "grade_level": seed["grade_level"],
            "default_timezone": "Asia/Bangkok",
            "updated_at": now,
        }
        if seed.get("active_term_id"):
            class_metadata["active_term_id"] = seed["active_term_id"]
        if seed.get("room_label"):
            class_metadata["room_label"] = seed["room_label"]
        if seed.get("homeroom_room"):
            class_metadata["homeroom_room"] = seed["homeroom_room"]

        operations.extend([
            SeedOperation(f"system/class_registry/{class_id}/main", registry_data),
            SeedOperation(f"classes/{class_id}/metadata/main", class_metadata),
        ])
        if seed.get("active_term_id"):
            term_metadata = {
                "term_id": seed["active_term_id"],
                "display_name": seed.get("term_display_name") or seed["active_term_id"],
                "status": "active",
                "updated_at": now,
            }
            operations.append(SeedOperation(f"classes/{class_id}/terms/{seed['active_term_id']}/metadata/main", term_metadata))
        if seed.get("active_term_id") and class_id in TIMETABLE_SEEDS:
            operations.append(SeedOperation(
                f"classes/{class_id}/terms/{seed['active_term_id']}/config/timetable",
                build_timetable_config(TIMETABLE_SEEDS[class_id], image_url=TIMETABLE_IMAGE_URLS.get(class_id)),
            ))
        if seed.get("active_term_id") and class_id in LINK_SEEDS:
            operations.append(SeedOperation(
                f"classes/{class_id}/terms/{seed['active_term_id']}/config/links",
                LINK_SEEDS[class_id],
            ))

    for invite_arg in invite_args or []:
        class_id, invite_code = _parse_invite_arg(invite_arg)
        operations.append(SeedOperation(
            f"class_invites/{invite_code}",
            {
                "class_id": class_id,
                "label": CLASS_SEEDS[class_id]["display_name"],
                "status": "active",
                "expires_at": None,
                "max_uses": None,
                "used_count": 0,
                "created_by": "seed_class_registry.py",
                "created_at": now,
                "updated_at": now,
            },
        ))

    return operations


def apply_seed_operations(db, operations: list[SeedOperation], dry_run: bool) -> None:
    for operation in operations:
        if dry_run:
            print(f"DRY RUN set {operation.path} merge={operation.merge}")
            print(json.dumps(operation.data, ensure_ascii=False, indent=2, sort_keys=True))
            continue

        doc_ref = _document_ref(db, operation.path)
        doc_ref.set(operation.data, merge=operation.merge)
        print(f"set {operation.path} merge={operation.merge}")


def connect_firestore():
    import firebase_admin
    from firebase_admin import credentials, firestore

    cred = _load_firebase_credentials(credentials)
    if cred is None:
        raise RuntimeError(
            "No Firebase credentials found. Set FIREBASE_CREDENTIALS_JSON or "
            "FIREBASE_CREDENTIALS_BASE64, or provide firebase_key.json locally."
        )
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    return firestore.client()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed MTC class registry foundation docs.")
    parser.add_argument("--apply", action="store_true", help="Write to Firestore. Omit for dry-run.")
    parser.add_argument(
        "--invite",
        action="append",
        default=[],
        metavar="CLASS_ID=INVITE_CODE",
        help="Optionally seed an explicit test invite. Example: --invite mtc13=TEST_MTC13",
    )
    args = parser.parse_args(argv)

    operations = build_seed_operations(args.invite)
    if not args.apply:
        apply_seed_operations(None, operations, dry_run=True)
        return 0

    db = connect_firestore()
    apply_seed_operations(db, operations, dry_run=False)
    return 0


def _document_ref(db, path: str):
    parts = path.split("/")
    if len(parts) % 2 != 0:
        raise ValueError(f"Firestore document path must have an even number of segments: {path}")

    ref = db.collection(parts[0]).document(parts[1])
    index = 2
    while index < len(parts):
        ref = ref.collection(parts[index]).document(parts[index + 1])
        index += 2
    return ref


def _parse_invite_arg(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise ValueError("--invite must use CLASS_ID=INVITE_CODE")
    class_id, invite_code = raw.split("=", 1)
    class_id = class_id.strip()
    invite_code = invite_code.strip().upper()
    if class_id not in CLASS_SEEDS or not is_valid_class_id(class_id):
        raise ValueError(f"Unsupported class_id for invite: {class_id}")
    if not is_valid_invite_code(invite_code):
        raise ValueError("Invite code must use A-Z, 0-9, _ or - and be 3-32 characters")
    return class_id, invite_code


def _load_firebase_credentials(credentials):
    raw = os.environ.get("FIREBASE_CREDENTIALS_JSON")
    if raw:
        return credentials.Certificate(json.loads(raw))

    b64 = os.environ.get("FIREBASE_CREDENTIALS_BASE64")
    if b64:
        decoded = base64.b64decode(b64).decode("utf-8")
        return credentials.Certificate(json.loads(decoded))

    key_path = ROOT / FIREBASE_KEY_PATH
    if key_path.exists():
        return credentials.Certificate(str(key_path))

    return None


if __name__ == "__main__":
    raise SystemExit(main())
