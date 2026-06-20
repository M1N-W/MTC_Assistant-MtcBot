# -*- coding: utf-8 -*-
"""MTC account Flex Message builder."""

from __future__ import annotations

from linebot.v3.messaging import FlexContainer, FlexMessage, TextMessage


NAVY = "#102033"
TEAL = "#0F766E"
MINT = "#2DD4BF"
IVORY = "#FFF7E6"
GOLD = "#D6A843"
AMBER = "#F6C453"
INK = "#16202A"
MUTED = "#5B6773"


def build_account_flex(account: dict) -> FlexMessage | TextMessage:
    try:
        return FlexMessage(
            alt_text="บัญชี MTC Assistant",
            contents=FlexContainer.from_dict(_content(account)),
        )
    except Exception:
        return TextMessage(text=_fallback_text(account))


def _content(account: dict) -> dict:
    verified = account.get("verification_status") == "verified"
    status_text = "ยืนยันตัวตนแล้ว" if verified else "ยังไม่ยืนยันตัวตน"
    status_color = GOLD if verified else AMBER
    rows = [
        _row("ชื่อ LINE", account.get("line_display_name") or "ไม่พบชื่อ LINE"),
        _row("สถานะ", status_text, status_color),
        _row("รุ่น", account.get("class_display") or "ยังไม่ได้เข้าห้อง"),
        _row("ระดับ", account.get("grade_level") or "ยังไม่ทราบ"),
        _row("ห้อง", account.get("room_label") or "ยังไม่ได้ตั้งค่าห้อง"),
        _row("ภาคเรียน", account.get("term_label") or "ยังไม่ได้ตั้งค่าภาคเรียน"),
        _row("ห้องที่ใช้งาน", account.get("active_class_label") or "ยังไม่ได้เลือกห้อง"),
        _row("บทบาท", account.get("role_label") or "นักเรียน"),
    ]
    if verified and account.get("identity_type") == "mtc_teacher":
        rows.insert(2, _row("ชื่อคุณครู", account.get("full_name") or "ไม่พบชื่อคุณครู"))
        assignment_text = "\n".join(account.get("assignment_labels") or ["ยังไม่ได้กำหนดหน้าที่"])
        rows.insert(3, _row("หน้าที่", assignment_text))
    elif verified:
        rows.insert(2, _row("ชื่อ–นามสกุล", account.get("full_name") or "ไม่พบชื่อจาก roster"))
        if account.get("class_number") is not None:
            rows.insert(3, _row("เลขที่", f"เลขที่ {account['class_number']}"))

    body_contents = [
        {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                _avatar(account),
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {"type": "text", "text": account.get("line_display_name") or "LINE User", "weight": "bold", "size": "lg", "color": INK, "wrap": True},
                        {"type": "text", "text": status_text, "size": "xs", "color": "#3A2A00", "weight": "bold", "margin": "sm"},
                    ],
                    "margin": "md",
                    "justifyContent": "center",
                },
            ],
        },
        {"type": "separator", "margin": "lg", "color": "#E4D6B8"},
        {"type": "box", "layout": "vertical", "contents": rows, "spacing": "sm", "margin": "lg"},
        _button("ยืนยันตัวตน", "ยืนยันตัวตน", TEAL),
        _button("เลือกห้อง" if not account.get("can_switch_class") else "เปลี่ยนห้อง", "เลือกห้อง", "#155E75"),
        _button("วิธีใช้งาน", "ช่วยเหลือ", "#4F46E5"),
        _button("แจ้งปัญหา", "แจ้งปัญหา", "#7C5E45"),
    ]
    return {
        "type": "bubble",
        "size": "mega",
        "hero": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "MTC ACCOUNT", "weight": "bold", "size": "lg", "color": "#FFFFFF", "align": "center"},
                {"type": "text", "text": "บัญชีของฉัน", "size": "sm", "color": "#DCEFF0", "align": "center", "margin": "sm"},
            ],
            "backgroundColor": NAVY,
            "paddingAll": "24px",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": body_contents,
            "backgroundColor": IVORY,
            "paddingAll": "18px",
            "spacing": "md",
        },
        "styles": {"body": {"backgroundColor": IVORY}},
    }


def _avatar(account: dict) -> dict:
    picture_url = account.get("line_picture_url")
    if picture_url:
        return {"type": "image", "url": picture_url, "size": "lg", "aspectRatio": "1:1", "aspectMode": "cover"}
    return {
        "type": "box",
        "layout": "vertical",
        "contents": [{"type": "text", "text": "MTC", "weight": "bold", "size": "md", "color": "#FFFFFF", "align": "center"}],
        "backgroundColor": TEAL,
        "cornerRadius": "12px",
        "width": "64px",
        "height": "64px",
        "justifyContent": "center",
    }


def _row(label: str, value, color: str = INK) -> dict:
    return {
        "type": "box",
        "layout": "horizontal",
        "contents": [
            {"type": "text", "text": label, "size": "xs", "color": MUTED, "flex": 4, "wrap": True},
            {"type": "text", "text": str(value or "-"), "size": "sm", "color": color, "weight": "bold", "flex": 6, "wrap": True},
        ],
    }


def _button(label: str, text: str, color: str) -> dict:
    return {
        "type": "button",
        "action": {"type": "message", "label": label, "text": text},
        "style": "primary",
        "height": "sm",
        "color": color,
        "margin": "sm",
    }


def _fallback_text(account: dict) -> str:
    return "\n".join([
        "MTC ACCOUNT",
        f"ชื่อ LINE: {account.get('line_display_name') or '-'}",
        f"สถานะ: {account.get('verification_status') or 'unverified'}",
        f"ห้องที่ใช้งาน: {account.get('active_class_label') or '-'}",
    ])
