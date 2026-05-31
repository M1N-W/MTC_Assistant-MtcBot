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


def get_links_menu_message(user_message: str = "", class_context=None, db=None) -> FlexMessage:
    """แสดงเมนูลิงก์ทั้งหมดด้วย Flex Message"""
    links = get_links_config(db, class_context)
    is_legacy = not class_context or getattr(class_context, "is_legacy_fallback", False)
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
                                        "type": "uri" if is_legacy else "message",
                                        "label": "🧬 ชีววิทยา",
                                        **({"uri": Bio_LINK} if is_legacy else {"text": "ชีวะ"})
                                    },
                                    "style": "primary",
                                    "color": "#10B981",
                                    "height": "sm",
                                    "flex": 1
                                },
                                {
                                    "type": "button",
                                    "action": {
                                        "type": "uri" if is_legacy else "message",
                                        "label": "⚛️ ฟิสิกส์",
                                        **({"uri": Physic_LINK} if is_legacy else {"text": "ฟิสิกส์"})
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
