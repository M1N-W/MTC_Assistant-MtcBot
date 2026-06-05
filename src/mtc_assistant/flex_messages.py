# -*- coding: utf-8 -*-
"""
MTC Assistant - Flex Message builders
"""

from linebot.v3.messaging import FlexMessage, FlexContainer

from mtc_assistant.config import Bio_LINK, Physic_LINK
from mtc_assistant.links_service import (
    ABSENCE_FORM_URL,
    GRADE_URL,
    SCHOOL_URL,
    get_links_config,
)


def _allows_legacy_solution_links(class_context) -> bool:
    return (
        not class_context
        or getattr(class_context, "is_legacy_fallback", False)
        or getattr(class_context, "class_id", None) == "mtc12"
    )


def _message_button(label: str, text: str, color: str = "#10B981") -> dict:
    return {
        "type": "button",
        "action": {
            "type": "message",
            "label": label,
            "text": text,
        },
        "style": "primary",
        "color": color,
        "height": "sm",
    }


def _button_row(left: dict, right: dict) -> dict:
    right = {**right, "margin": "sm"}
    return {
        "type": "box",
        "layout": "horizontal",
        "contents": [
            {**left, "flex": 1},
            {**right, "flex": 1},
        ],
        "spacing": "sm",
        "margin": "sm",
    }


def _section(title: str, examples: str | None = None, rows: list[dict] | None = None) -> dict:
    contents = [
        {
            "type": "text",
            "text": title,
            "weight": "bold",
            "size": "md",
            "color": "#111827",
            "wrap": True,
        }
    ]
    if rows:
        contents.extend(rows)
    if examples:
        contents.append({
            "type": "text",
            "text": examples,
            "size": "xs",
            "color": "#4B5563",
            "wrap": True,
            "margin": "sm",
        })
    return {
        "type": "box",
        "layout": "vertical",
        "contents": contents,
        "spacing": "xs",
        "margin": "lg",
    }


def get_help_menu_message(user_message: str = "") -> FlexMessage:
    """Build the student-facing help menu."""
    flex_content = {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "MTC Assistant",
                    "weight": "bold",
                    "size": "xl",
                    "color": "#FFFFFF",
                    "wrap": True,
                },
                {
                    "type": "text",
                    "text": "ผู้ช่วยประจำห้องเรียน",
                    "size": "sm",
                    "color": "#DCFCE7",
                    "margin": "xs",
                    "wrap": True,
                },
            ],
            "backgroundColor": "#047857",
            "paddingAll": "20px",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                _section(
                    "การเรียน",
                    "เช็คเวลาเรียน / ปลายภาค",
                    [
                        _button_row(
                            _message_button("ตารางเรียน", "ตารางเรียน", "#059669"),
                            _message_button("คาบต่อไป", "คาบต่อไป", "#0D9488"),
                        ),
                        _button_row(
                            _message_button("กลางภาค", "กลางภาค", "#2563EB"),
                            _message_button("ปลายภาค", "ปลายภาค", "#1D4ED8"),
                        ),
                    ],
                ),
                _section(
                    "การบ้าน",
                    "งาน",
                    [
                        _button_row(
                            _message_button("บันทึกการบ้าน", "บันทึกการบ้าน", "#7C3AED"),
                            _message_button("การบ้าน", "การบ้าน", "#9333EA"),
                        ),
                    ],
                ),
                _section(
                    "ลิงก์สำคัญ",
                    "เว็บโรงเรียน / เกรด / ลา",
                    [
                        _button_row(
                            _message_button("ลิงก์", "ลิงก์", "#0891B2"),
                            _message_button("เว็บโรงเรียน", "เว็บโรงเรียน", "#0E7490"),
                        ),
                    ],
                ),
                _section(
                    "เฉลยวิชา",
                    "ชีวะ / ฟิสิกส์",
                    [
                        _button_row(
                            _message_button("ชีวะ", "ชีวะ", "#16A34A"),
                            _message_button("ฟิสิกส์", "ฟิสิกส์", "#4F46E5"),
                        ),
                    ],
                ),
                _section(
                    "คำนวณ / AI",
                    "คำนวณ [สมการ]\nพิมพ์คำถามอื่น ๆ เพื่อถาม AI ได้",
                ),
            ],
            "paddingAll": "18px",
            "spacing": "sm",
        },
    }

    return FlexMessage(
        alt_text="คำสั่งที่ใช้ได้ของ MTC Assistant",
        contents=FlexContainer.from_dict(flex_content),
    )


def get_links_menu_message(user_message: str = "", class_context=None, db=None) -> FlexMessage:
    """แสดงเมนูลิงก์ทั้งหมดด้วย Flex Message"""
    links = get_links_config(db, class_context)
    allows_solution_links = _allows_legacy_solution_links(class_context)
    flex_content = {
        "type": "bubble",
        "size": "mega",
        "hero": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "🔗",
                            "size": "xxl",
                            "color": "#FFFFFF",
                            "align": "center",
                            "weight": "bold"
                        },
                        {
                            "type": "text",
                            "text": "ลิงก์สำคัญ",
                            "size": "xl",
                            "color": "#FFFFFF",
                            "align": "center",
                            "weight": "bold",
                            "margin": "md"
                        },
                        {
                            "type": "text",
                            "text": "เข้าถึงง่าย ครบจบในที่เดียว",
                            "size": "sm",
                            "color": "#FFFFFF",
                            "align": "center",
                            "margin": "sm",
                            "opacity": 0.8
                        }
                    ],
                    "paddingAll": "30px"
                }
            ],
            "backgroundColor": "#7C3AED",
            "paddingAll": "0px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "📚 การเรียน",
                            "weight": "bold",
                            "size": "lg",
                            "color": "#1A1A1A"
                        },
                        {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "uri",
                                        "label": "🏫 เว็บโรงเรียน",
                                        "uri": links[SCHOOL_URL]
                                    },
                                    "style": "primary",
                                    "color": "#00C300",
                                    "height": "sm"
                                },
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "uri",
                                        "label": "📊 ระบบเช็คเกรด",
                                        "uri": links[GRADE_URL]
                                    },
                                    "style": "primary",
                                    "color": "#3B82F6",
                                    "height": "sm",
                                    "margin": "sm"
                                },
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "uri",
                                        "label": "📝 แบบฟอร์มลาออนไลน์",
                                        "uri": links[ABSENCE_FORM_URL]
                                    },
                                    "style": "primary",
                                    "color": "#F59E0B",
                                    "height": "sm",
                                    "margin": "sm"
                                }
                            ],
                            "margin": "md"
                        }
                    ],
                    "paddingAll": "0px"
                },
                {
                    "type": "separator",
                    "margin": "xl"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "📖 เฉลยวิชา",
                            "weight": "bold",
                            "size": "lg",
                            "color": "#1A1A1A"
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "uri" if allows_solution_links else "message",
                                        "label": "🧬 ชีววิทยา",
                                        **({"uri": Bio_LINK} if allows_solution_links else {"text": "ชีวะ"})
                                    },
                                    "style": "primary",
                                    "color": "#10B981",
                                    "height": "sm",
                                    "flex": 1
                                },
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "uri" if allows_solution_links else "message",
                                        "label": "⚛️ ฟิสิกส์",
                                        **({"uri": Physic_LINK} if allows_solution_links else {"text": "ฟิสิกส์"})
                                    },
                                    "style": "primary",
                                    "color": "#8B5CF6",
                                    "height": "sm",
                                    "flex": 1,
                                    "margin": "sm"
                                }
                            ],
                            "margin": "md"
                        }
                    ],
                    "margin": "xl"
                },
                {
                    "type": "separator",
                    "margin": "xl"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "🎵 ความบันเทิง",
                            "weight": "bold",
                            "size": "lg",
                            "color": "#1A1A1A"
                        },
                        {
                            "type": "button",
                            "action": {
                                "type": "message",
                                "label": "ค้นหาเพลงใน YouTube",
                                "text": "เปิดเพลง"
                            },
                            "style": "primary",
                            "color": "#EC4899",
                            "height": "sm",
                            "margin": "md"
                        }
                    ],
                    "margin": "xl"
                }
            ],
            "paddingAll": "20px"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": "💡",
                            "size": "sm",
                            "flex": 0
                        },
                        {
                            "type": "text",
                            "text": "บันทึกลิงก์ที่ใช้บ่อยไว้เพื่อเข้าถึงได้เร็วขึ้น",
                            "size": "xs",
                            "color": "#999999",
                            "wrap": True,
                            "flex": 1,
                            "margin": "sm"
                        }
                    ]
                }
            ],
            "backgroundColor": "#F9FAFB",
            "paddingAll": "16px"
        }
    }

    return FlexMessage(
        alt_text="ลิงก์สำคัญทั้งหมด",
        contents=FlexContainer.from_dict(flex_content)
    )
