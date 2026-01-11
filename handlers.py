# -*- coding: utf-8 -*-
"""
MTC Assistant - Handlers Module (Enhanced Flex Message)
แก้ไข Flex Message ให้สวยงามและทุกปุ่มมีสี
"""

import time
import threading
from typing import Dict, List, Optional, Union, Callable
from flask import request

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, 
    TextMessage, ImageMessage, FlexMessage, FlexContainer
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

# Import from config
from config import (
    logger, ACCESS_TOKEN, CHANNEL_SECRET, MESSAGES,
    RATE_LIMIT_MAX, RATE_LIMIT_WINDOW, ADMIN_USER_IDS,
    SCHOOL_LINK, GRADE_LINK, ABSENCE_LINK, Bio_LINK, Physic_LINK
)

# Import from features
from features import (
    get_worksheet_message, get_school_link_message, get_timetable_image_message,
    get_grade_link_message, get_absence_form_message, get_bio_link_message,
    get_physic_link_message, get_help_message, get_next_class_message,
    get_time_until_next_class_message, get_exam_countdown_message,
    get_music_link_message, get_gemini_response,
    add_homework_to_db, get_homeworks_from_db, clear_homework_db
)

# Import broadcast functions
import broadcast

# ============================================================================
# LINE BOT CONFIGURATION
# ============================================================================
configuration = Configuration(access_token=ACCESS_TOKEN) if ACCESS_TOKEN else None
handler = WebhookHandler(CHANNEL_SECRET) if CHANNEL_SECRET else None

# ============================================================================
# CONNECTION POOLING
# ============================================================================
_line_api_client: Optional[MessagingApi] = None
_api_client_lock = threading.Lock()

def get_line_api() -> Optional[MessagingApi]:
    """Get or create LINE API client (singleton pattern)"""
    global _line_api_client
    
    if _line_api_client is None and configuration:
        with _api_client_lock:
            if _line_api_client is None:
                try:
                    _line_api_client = MessagingApi(ApiClient(configuration))
                    logger.debug("LINE API client initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize LINE API client: {e}")
    
    return _line_api_client

# ============================================================================
# RATE LIMITING
# ============================================================================
_user_message_history: Dict[str, List[float]] = {}
_rate_limit_lock = threading.Lock()
_banned_users: Dict[str, float] = {}

def is_rate_limited(user_id: str) -> bool:
    """Check if user is rate limited"""
    now_ts = time.time()
    
    with _rate_limit_lock:
        if user_id in _banned_users:
            ban_until = _banned_users[user_id]
            if now_ts < ban_until:
                remaining = int(ban_until - now_ts)
                logger.warning(f"User {user_id} is banned for {remaining}s")
                return True
            else:
                del _banned_users[user_id]
        
        history = _user_message_history.get(user_id, [])
        recent = [t for t in history if now_ts - t < RATE_LIMIT_WINDOW]
        
        if len(recent) > RATE_LIMIT_MAX * 3:
            _banned_users[user_id] = now_ts + 300
            logger.error(f"User {user_id} BANNED for severe abuse")
            return True
        
        if len(recent) > RATE_LIMIT_MAX * 2:
            logger.warning(f"User {user_id} in extended cooldown")
            return True
        
        recent.append(now_ts)
        _user_message_history[user_id] = recent
        
        if len(recent) > RATE_LIMIT_MAX:
            logger.info(f"User {user_id} rate limited")
            return True
    
    return False

def get_rate_limit_status(user_id: str) -> dict:
    """Get rate limit status"""
    now_ts = time.time()
    
    with _rate_limit_lock:
        if user_id in _banned_users:
            return {
                "status": "banned",
                "ban_until": _banned_users[user_id],
                "remaining_seconds": int(_banned_users[user_id] - now_ts)
            }
        
        history = _user_message_history.get(user_id, [])
        recent = [t for t in history if now_ts - t < RATE_LIMIT_WINDOW]
        
        return {
            "status": "rate_limited" if len(recent) > RATE_LIMIT_MAX else "ok",
            "messages_count": len(recent),
            "limit": RATE_LIMIT_MAX,
            "window_seconds": RATE_LIMIT_WINDOW
        }

# ============================================================================
# FLEX MESSAGE - ENHANCED LINKS MENU
# ============================================================================

def get_links_menu_message(user_message: str = "") -> FlexMessage:
    """แสดงเมนูลิงก์ทั้งหมดด้วย Flex Message (Enhanced Design)"""
    
    flex_content = {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "🔗 ลิงก์สำคัญทั้งหมด",
                    "weight": "bold",
                    "size": "xl",
                    "color": "#FFFFFF"
                },
                {
                    "type": "text",
                    "text": "เลือกลิงก์ที่ต้องการเข้าถึง",
                    "size": "xs",
                    "color": "#FFFFFF",
                    "margin": "sm",
                    "wrap": True
                }
            ],
            "backgroundColor": "#7C3AED",
            "paddingAll": "20px"
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                # Section 1: การเรียน
                {
                    "type": "text",
                    "text": "📚 การเรียน",
                    "weight": "bold",
                    "size": "md",
                    "color": "#666666",
                    "margin": "none"
                },
                {
                    "type": "separator",
                    "margin": "sm"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "🏫 เว็บโรงเรียน",
                        "uri": SCHOOL_LINK
                    },
                    "style": "primary",
                    "color": "#00C300",
                    "height": "sm",
                    "margin": "md"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "📊 เช็คเกรด",
                        "uri": GRADE_LINK
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
                        "label": "📝 แบบฟอร์มลา",
                        "uri": ABSENCE_LINK
                    },
                    "style": "primary",
                    "color": "#F59E0B",
                    "height": "sm",
                    "margin": "sm"
                },
                # Section 2: เฉลยวิชา
                {
                    "type": "text",
                    "text": "📖 เฉลยวิชา",
                    "weight": "bold",
                    "size": "md",
                    "color": "#666666",
                    "margin": "xl"
                },
                {
                    "type": "separator",
                    "margin": "sm"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "🧬 เฉลยชีววิทยา",
                        "uri": Bio_LINK
                    },
                    "style": "primary",
                    "color": "#10B981",
                    "height": "sm",
                    "margin": "md"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "⚛️ เฉลยฟิสิกส์",
                        "uri": Physic_LINK
                    },
                    "style": "primary",
                    "color": "#8B5CF6",
                    "height": "sm",
                    "margin": "sm"
                },
                # Section 3: ความบันเทิง
                {
                    "type": "text",
                    "text": "🎵 ความบันเทิง",
                    "weight": "bold",
                    "size": "md",
                    "color": "#666666",
                    "margin": "xl"
                },
                {
                    "type": "separator",
                    "margin": "sm"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "message",
                        "label": "🎵 ค้นหาเพลง",
                        "text": "เปิดเพลง"
                    },
                    "style": "primary",
                    "color": "#EC4899",
                    "height": "sm",
                    "margin": "md"
                }
            ],
            "spacing": "none",
            "paddingAll": "20px"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "💡 Tip: บันทึกลิงก์ที่ใช้บ่อยไว้",
                    "size": "xxs",
                    "color": "#999999",
                    "align": "center",
                    "wrap": True
                }
            ],
            "backgroundColor": "#F3F4F6",
            "paddingAll": "12px"
        }
    }
    
    return FlexMessage(
        alt_text="🔗 ลิงก์สำคัญทั้งหมด - MTC Assistant",
        contents=FlexContainer.from_dict(flex_content)
    )

# ============================================================================
# COMMAND MATCHING
# ============================================================================

def _keyword_matches(message_lower: str, keyword_lower: str) -> bool:
    """Check if keyword matches"""
    return keyword_lower in message_lower

def call_action(action: Callable, user_message: str) -> Union[TextMessage, ImageMessage, FlexMessage]:
    """Call action function"""
    try:
        if action.__code__.co_argcount > 0:
            return action(user_message)
        else:
            return action()
    except Exception as e:
        logger.exception(f"Error calling action {action.__name__}: {e}")
        return TextMessage(text=MESSAGES.get("ACTION_ERROR", "เกิดข้อผิดพลาด"))

# ============================================================================
# COMMANDS LIST - รองรับ Rich Menu
# ============================================================================

COMMANDS = [
    # Rich Menu Commands
    (("ตารางเรียน", "ตารางสอน"), get_timetable_image_message),
    (("เช็คเวลาเรียน", "เช็คเวลา", "ดูเวลาเรียน"), get_time_until_next_class_message),
    (("บันทึกการบ้าน", "บันทึกงาน", "ดูงาน"), lambda msg: TextMessage(text=get_homeworks_from_db())),
    (("ลิงก์ที่สำคัญ", "ลิงค์สำคัญ", "ลิงก์", "links"), get_links_menu_message),
    (("ปฏิทินกิจกรรม", "ปฏิทิน", "กิจกรรม", "ดูกิจกรรม"), get_exam_countdown_message),
    (("ช่วยเหลือ", "คำสั่ง", "help"), get_help_message),
    
    # Other Commands
    (("งาน", "การบ้าน", "เช็คงาน", "ใบงาน"), get_worksheet_message),
    (("เว็บโรงเรียน", "เว็บ"), get_school_link_message),
    (("เกรด", "ดูเกรด"), get_grade_link_message),
    (("ลาป่วย", "ลากิจ", "ลา"), get_absence_form_message),
    (("ชีวะ", "เฉลยชีวะ"), get_bio_link_message),
    (("ฟิสิกส์", "เฉลยฟิสิกส์"), get_physic_link_message),
    (("คาบต่อไป", "เรียนอะไร", "เรียนไรต่อ"), get_next_class_message),
    (("อีกกี่นาที", "เหลือเวลา"), get_time_until_next_class_message),
    (("สอบ", "วันสอบ", "นับถอยหลังสอบ"), get_exam_countdown_message),
    (("เปิดเพลง", "หาเพลง", "ขอเพลง"), get_music_link_message),
]

# ============================================================================
# LINE REPLY HELPER
# ============================================================================

def reply_to_line(reply_token: str, messages: List[Union[TextMessage, ImageMessage, FlexMessage]]) -> bool:
    """Send reply to LINE"""
    if not messages:
        logger.warning("No messages to send")
        return False
    
    line_bot_api = get_line_api()
    if not line_bot_api:
        logger.error("LINE API client not available")
        return False
    
    try:
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages
            )
        )
        logger.debug(f"Successfully replied with {len(messages)} message(s)")
        return True
    except Exception as e:
        logger.error(f"LINE Reply Error: {e}")
        return False

# ============================================================================
# EVENT HANDLERS
# ============================================================================

@handler.add(FollowEvent) if handler else (lambda f: f)
def handle_follow(event):
    """Handle user following"""
    welcome_message = TextMessage(
        text='👋 สวัสดีครับ! ผมคือ MTC Assistant\n'
             'ผู้ช่วยอเนกประสงค์ของห้อง ม.4/2\n\n'
             'พิมพ์ "คำสั่ง" เพื่อดูรายการคำสั่งทั้งหมดนะครับ'
    )
    try:
        reply_to_line(event.reply_token, [welcome_message])
        logger.info("Sent follow welcome message")
    except Exception as e:
        logger.exception(f"Failed to send follow reply: {e}")

@handler.add(MessageEvent, message=TextMessageContent) if handler else (lambda f: f)
def handle_message(event):
    """Handle incoming text messages"""
    user_text = getattr(event.message, "text", "")
    user_message = user_text.strip()
    
    if not user_message:
        reply_to_line(event.reply_token, [TextMessage(text=MESSAGES["INVALID_MESSAGE"])])
        return
    
    # Get user ID
    user_id = None
    try:
        user_id = event.source.user_id if hasattr(event, "source") else None
    except Exception:
        user_id = None
    
    if not user_id:
        user_id = f"anon-{request.remote_addr or 'unknown'}"
    
    logger.info("Message from %s: %s", user_id, user_message[:100])
    
    # Track user for broadcast
    try:
        broadcast.track_user(user_id)
    except Exception as e:
        logger.error(f"Failed to track user: {e}")
    
    # Check rate limit
    if is_rate_limited(user_id):
        rate_status = get_rate_limit_status(user_id)
        if rate_status["status"] == "banned":
            reply_message = TextMessage(
                text=f"⛔ คุณถูกระงับชั่วคราวเนื่องจากส่งข้อความมากเกินไป\n"
                     f"กรุณารออีก {rate_status['remaining_seconds']} วินาที"
            )
        else:
            reply_message = TextMessage(text=MESSAGES["RATE_LIMITED"])
        
        reply_to_line(event.reply_token, [reply_message])
        return
    
    user_message_lower = user_message.lower()
    reply_message = None
    
    # Admin Commands
    if user_id in ADMIN_USER_IDS:
        if user_message.startswith("ประกาศ "):
            message_to_broadcast = user_message.replace("ประกาศ ", "", 1).strip()
            if message_to_broadcast:
                announcement = broadcast.create_announcement("ประกาศจากผู้ดูแล", message_to_broadcast)
                result = broadcast.broadcast_message(announcement)
                broadcast.save_broadcast_history(user_id, announcement, result)
                reply_message = TextMessage(text=result['message'])
            else:
                reply_message = TextMessage(text="⚠️ รูปแบบ: ประกาศ [ข้อความ]")
        
        elif user_message.startswith("ประกาศด่วน "):
            urgent_msg = user_message.replace("ประกาศด่วน ", "", 1).strip()
            if urgent_msg:
                alert = broadcast.create_urgent_alert(urgent_msg)
                result = broadcast.broadcast_message(alert)
                broadcast.save_broadcast_history(user_id, alert, result)
                reply_message = TextMessage(text=result['message'])
            else:
                reply_message = TextMessage(text="⚠️ รูปแบบ: ประกาศด่วน [ข้อความ]")
        
        elif user_message.startswith("เตือนการบ้าน "):
            reminder_msg = user_message.replace("เตือนการบ้าน ", "", 1).strip()
            if reminder_msg:
                reminder = broadcast.create_reminder("การบ้าน", reminder_msg)
                result = broadcast.broadcast_message(reminder)
                broadcast.save_broadcast_history(user_id, reminder, result)
                reply_message = TextMessage(text=result['message'])
            else:
                reply_message = TextMessage(text="⚠️ รูปแบบ: เตือนการบ้าน [รายละเอียด]")
        
        elif user_message in ["สถิติประกาศ", "broadcast stats"]:
            reply_message = TextMessage(text=broadcast.get_broadcast_stats())
        
        elif user_message in ["จำนวนผู้ใช้", "user count", "ผู้ใช้"]:
            count = broadcast.get_user_count()
            reply_message = TextMessage(text=f"👥 จำนวนผู้ใช้ทั้งหมด: {count} คน")
        
        elif user_message in ["admin", "คำสั่งแอดมิน"]:
            admin_help = (
                "👨‍💼 *คำสั่งแอดมิน*\n\n"
                "📢 *การประกาศ:*\n"
                "• ประกาศ [ข้อความ]\n"
                "• ประกาศด่วน [ข้อความ]\n"
                "• เตือนการบ้าน [รายละเอียด]\n\n"
                "📊 *สถิติ:*\n"
                "• สถิติประกาศ\n"
                "• จำนวนผู้ใช้"
            )
            reply_message = TextMessage(text=admin_help)

    # วิธีสั่งการบ้าน
    if not reply_message and "วิธีสั่งการบ้าน" in user_message:
        instruction_msg = (
            "📝 วิธีสั่งการบ้าน\n\n"
            "พิมพ์: สั่งการบ้าน | วิชา | รายละเอียด | วันส่ง\n\n"
            "💡 ตัวอย่าง\n"
            "สั่งการบ้าน | คณิต | แบบฝึกหัด | วันศุกร์"
        )
        reply_to_line(event.reply_token, [TextMessage(text=instruction_msg)])
        return
    
    # Firebase Commands
    if not reply_message and user_message.startswith("สั่งการบ้าน"):
        reply_message = _handle_add_homework(user_message)
    
    elif not reply_message and user_message in ["การบ้าน", "ดูการบ้าน", "homework"]:
        reply_message = TextMessage(text=get_homeworks_from_db())
    
    elif not reply_message and user_message in ["ลบการบ้านทั้งหมด", "clear hw", "ลบงาน"]:
        reply_message = TextMessage(text=clear_homework_db())
    
    # Try Standard Commands
    if not reply_message:
        for keywords, action in COMMANDS:
            matched = False
            for keyword in sorted(keywords, key=len, reverse=True):
                if _keyword_matches(user_message_lower, keyword.lower()):
                    try:
                        reply_message = call_action(action, user_message)
                        logger.debug("Matched command: %s", keyword)
                    except Exception as e:
                        logger.exception("Error executing action: %s", e)
                        reply_message = TextMessage(text=MESSAGES["ACTION_ERROR"])
                    matched = True
                    break
            
            if matched:
                break
    
    # Fallback to Gemini AI
    if not reply_message:
        logger.debug("No command matched, using Gemini API")
        try:
            ai_response_text = get_gemini_response(user_message)
            reply_message = TextMessage(text=ai_response_text)
        except Exception as e:
            logger.exception(f"Gemini API error: {e}")
            reply_message = TextMessage(text=MESSAGES["AI_ERROR"])
    
    # Send Reply
    try:
        if reply_message:
            success = reply_to_line(event.reply_token, [reply_message])
            if not success:
                logger.error("Failed to send reply")
        else:
            logger.warning("No reply generated")
    except Exception as e:
        logger.exception(f"Failed to send reply: {e}")

# ============================================================================
# HOMEWORK HANDLER
# ============================================================================

def _handle_add_homework(user_message: str) -> TextMessage:
    """Handle add homework command"""
    if "|" in user_message:
        parts = [p.strip() for p in user_message.split("|")]
        if len(parts) >= 3:
            subject = parts[1][:100]
            detail = parts[2][:500]
            due = parts[3][:50] if len(parts) > 3 else "ไม่ระบุ"
            
            if not subject:
                return TextMessage(text="⚠️ กรุณาระบุชื่อวิชา")
            if not detail:
                return TextMessage(text="⚠️ กรุณาระบุรายละเอียด")
            
            result = add_homework_to_db(subject, detail, due)
            return TextMessage(text=result)
        else:
            return TextMessage(
                text="⚠️ รูปแบบ: สั่งการบ้าน | วิชา | รายละเอียด | วันส่ง\n"
                     "ตัวอย่าง: สั่งการบ้าน | ฟิสิกส์ | ทำแบบฝึกหัด | วันศุกร์"
            )
    else:
        return TextMessage(
            text="⚠️ รูปแบบที่แนะนำ: สั่งการบ้าน | วิชา | รายละเอียด | วันส่ง"
        )

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'handler',
    'configuration',
    'handle_follow',
    'handle_message',
    'reply_to_line',
    'is_rate_limited',
    'get_rate_limit_status',
    'get_line_api',
    'get_links_menu_message',
]
