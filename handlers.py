# -*- coding: utf-8 -*-
"""
MTC Assistant - Handlers Module (FULLY INTEGRATED)
✅ All features integrated: exam, blacklist, impersonate, food, calculator, grade
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
    add_homework_to_db, get_homeworks_from_db, clear_homework_db,
    get_calculator_response, get_grade_calculator_response
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

# ============================================================================
# FLEX MESSAGE - LINKS MENU
# ============================================================================

def get_links_menu_message(user_message: str = "") -> FlexMessage:
    """แสดงเมนูลิงก์ทั้งหมดด้วย Flex Message"""
    
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
                {"type": "text", "text": "📚 การเรียน", "weight": "bold", "size": "md", "color": "#666666", "margin": "none"},
                {"type": "separator", "margin": "sm"},
                {"type": "button", "action": {"type": "uri", "label": "🏫 เว็บโรงเรียน", "uri": SCHOOL_LINK}, "style": "primary", "color": "#00C300", "height": "sm", "margin": "md"},
                {"type": "button", "action": {"type": "uri", "label": "📊 เช็คเกรด", "uri": GRADE_LINK}, "style": "primary", "color": "#3B82F6", "height": "sm", "margin": "sm"},
                {"type": "button", "action": {"type": "uri", "label": "📝 แบบฟอร์มลา", "uri": ABSENCE_LINK}, "style": "primary", "color": "#F59E0B", "height": "sm", "margin": "sm"},
                {"type": "text", "text": "📖 เฉลยวิชา", "weight": "bold", "size": "md", "color": "#666666", "margin": "xl"},
                {"type": "separator", "margin": "sm"},
                {"type": "button", "action": {"type": "uri", "label": "🧬 เฉลยชีววิทยา", "uri": Bio_LINK}, "style": "primary", "color": "#10B981", "height": "sm", "margin": "md"},
                {"type": "button", "action": {"type": "uri", "label": "⚛️ เฉลยฟิสิกส์", "uri": Physic_LINK}, "style": "primary", "color": "#8B5CF6", "height": "sm", "margin": "sm"},
                {"type": "text", "text": "🎵 ความบันเทิง", "weight": "bold", "size": "md", "color": "#666666", "margin": "xl"},
                {"type": "separator", "margin": "sm"},
                {"type": "button", "action": {"type": "message", "label": "🎵 ค้นหาเพลง", "text": "เปิดเพลง"}, "style": "primary", "color": "#EC4899", "height": "sm", "margin": "md"}
            ],
            "spacing": "none",
            "paddingAll": "20px"
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [{"type": "text", "text": "💡 Tip: บันทึกลิงก์ที่ใช้บ่อยไว้", "size": "xxs", "color": "#999999", "align": "center", "wrap": True}],
            "backgroundColor": "#F3F4F6",
            "paddingAll": "12px"
        }
    }
    
    return FlexMessage(alt_text="🔗 ลิงก์สำคัญทั้งหมด", contents=FlexContainer.from_dict(flex_content))

# ============================================================================
# COMMANDS LIST
# ============================================================================

COMMANDS = [
    (("ตารางเรียน", "ตารางสอน"), get_timetable_image_message),
    (("เช็คเวลาเรียน", "เช็คเวลา"), get_time_until_next_class_message),
    (("บันทึกการบ้าน", "ดูงาน"), lambda msg: TextMessage(text=get_homeworks_from_db())),
    (("ลิงก์ที่สำคัญ", "ลิงก์", "links"), get_links_menu_message),
    (("ปฏิทินกิจกรรม", "ปฏิทิน"), get_exam_countdown_message),
    (("ช่วยเหลือ", "คำสั่ง", "help"), get_help_message),
    (("งาน", "การบ้าน", "ใบงาน"), get_worksheet_message),
    (("เว็บโรงเรียน", "เว็บ"), get_school_link_message),
    (("เกรด", "ดูเกรด"), get_grade_link_message),
    (("ลา",), get_absence_form_message),
    (("ชีวะ",), get_bio_link_message),
    (("ฟิสิกส์",), get_physic_link_message),
    (("คาบต่อไป",), get_next_class_message),
    (("อีกกี่นาที",), get_time_until_next_class_message),
    (("สอบ", "วันสอบ"), get_exam_countdown_message),
    (("เปิดเพลง", "หาเพลง"), get_music_link_message),
]

# ============================================================================
# LINE REPLY HELPER
# ============================================================================

def reply_to_line(reply_token: str, messages: List[Union[TextMessage, ImageMessage, FlexMessage]]) -> bool:
    """Send reply to LINE"""
    if not messages:
        return False
    
    line_bot_api = get_line_api()
    if not line_bot_api:
        return False
    
    try:
        line_bot_api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=messages))
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
    welcome_message = TextMessage(text='👋 สวัสดีครับ! ผมคือ MTC Assistant\nพิมพ์ "คำสั่ง" เพื่อดูรายการคำสั่งทั้งหมด')
    try:
        reply_to_line(event.reply_token, [welcome_message])
    except Exception as e:
        logger.exception(f"Failed to send follow reply: {e}")

@handler.add(MessageEvent, message=TextMessageContent) if handler else (lambda f: f)
def handle_message(event):
    """Handle incoming text messages - FULLY INTEGRATED"""
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
    
    # ========================================================================
    # 🚫 CHECK BLACKLIST (CRITICAL - FIRST CHECK!)
    # ========================================================================
    try:
        from user_blacklist import check_user_banned
        is_banned, ban_message = check_user_banned(user_id)
        if is_banned:
            reply_to_line(event.reply_token, [TextMessage(text=ban_message)])
            logger.warning(f"Banned user {user_id} attempted to use bot")
            return
    except ImportError:
        pass  # Blacklist module not available
    except Exception as e:
        logger.error(f"Blacklist check error: {e}")
    
    # Track user for broadcast & impersonate
    try:
        broadcast.track_user(user_id)
        
        # Track for impersonate feature
        try:
            from admin_impersonate import track_user_activity
            track_user_activity(user_id)
        except ImportError:
            pass
    except Exception as e:
        logger.error(f"Failed to track user: {e}")
    
    # Check rate limit
    if is_rate_limited(user_id):
        reply_to_line(event.reply_token, [TextMessage(text=MESSAGES["RATE_LIMITED"])])
        return
    
    user_message_lower = user_message.lower()
    reply_message = None
    
    # ========================================================================
    # 👨‍💼 ADMIN COMMANDS
    # ========================================================================
    if user_id in ADMIN_USER_IDS:
        # Broadcast commands
        if user_message.startswith("ประกาศ "):
            msg = user_message.replace("ประกาศ ", "", 1).strip()
            if msg:
                announcement = broadcast.create_announcement("ประกาศจากผู้ดูแล", msg)
                result = broadcast.broadcast_message(announcement)
                broadcast.save_broadcast_history(user_id, announcement, result)
                reply_message = TextMessage(text=result['message'])
        
        elif user_message in ["สถิติประกาศ", "broadcast stats"]:
            reply_message = TextMessage(text=broadcast.get_broadcast_stats())
        
        elif user_message in ["จำนวนผู้ใช้", "user count"]:
            count = broadcast.get_user_count()
            reply_message = TextMessage(text=f"👥 จำนวนผู้ใช้: {count} คน")
        
        # Impersonate commands
        try:
            from admin_impersonate import (
                handle_list_users_command,
                handle_send_impersonate_command,
                handle_test_impersonate_command
            )
            
            if user_message in ["ดูผู้ใช้", "users list"]:
                reply_message = TextMessage(text=handle_list_users_command(user_id))
            
            elif user_message.startswith("ส่งถึง "):
                reply_message = TextMessage(text=handle_send_impersonate_command(user_id, user_message))
            
            elif user_message.startswith("ทดสอบส่ง "):
                reply_message = TextMessage(text=handle_test_impersonate_command(user_id, user_message))
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"Impersonate error: {e}")
        
        # Blacklist commands
        try:
            from user_blacklist import (
                handle_ban_user_command,
                handle_unban_user_command,
                handle_list_banned_command,
                handle_ban_stats_command
            )
            
            if user_message.startswith("แบน "):
                reply_message = TextMessage(text=handle_ban_user_command(user_id, user_message))
            
            elif user_message.startswith("ปลดแบน "):
                reply_message = TextMessage(text=handle_unban_user_command(user_id, user_message))
            
            elif user_message in ["รายชื่อแบน", "banned list"]:
                reply_message = TextMessage(text=handle_list_banned_command(user_id))
            
            elif user_message in ["สถิติแบน", "ban stats"]:
                reply_message = TextMessage(text=handle_ban_stats_command(user_id))
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"Blacklist error: {e}")
        
        # Admin help
        if user_message in ["admin", "คำสั่งแอดมิน"]:
            admin_help = (
                "👨‍💼 *คำสั่งแอดมิน*\n\n"
                "📢 ประกาศ [ข้อความ]\n"
                "📊 สถิติประกาศ\n"
                "👥 จำนวนผู้ใช้\n\n"
                "🎭 *Impersonate:*\n"
                "👀 ดูผู้ใช้\n"
                "✉️ ส่งถึง [user_id] [ข้อความ]\n\n"
                "🚫 *Blacklist:*\n"
                "⛔ แบน [user_id] [เหตุผล]\n"
                "✅ ปลดแบน [user_id]\n"
                "📋 รายชื่อแบน"
            )
            reply_message = TextMessage(text=admin_help)
    
    # ========================================================================
    # 📚 EXAM SIMULATOR
    # ========================================================================
    if not reply_message:
        try:
            from exam_simulator import (
                get_session_manager,
                handle_start_exam_command,
                handle_answer_command,
                handle_show_current_question,
                handle_cancel_exam,
                handle_show_explanation,
                handle_exam_stats
            )
            from features import gemini_client_primary, gemini_model_primary
            
            from main import db
            exam_mgr = get_session_manager(db)
            
            # Check if in exam session
            if exam_mgr.has_active_session(user_id):
                # Answer question
                if user_message.strip().isdigit() or any(x in user_message_lower for x in ['ตอบ', 'คือ']):
                    msg_text, send_next = handle_answer_command(user_id, user_message, db)
                    
                    if msg_text:
                        reply_to_line(event.reply_token, [TextMessage(text=msg_text)])
                        return
                    
                    if send_next:
                        next_q = handle_show_current_question(user_id, db)
                        reply_to_line(event.reply_token, [TextMessage(text=next_q)])
                        return
            
            # Start exam
            if any(kw in user_message_lower for kw in ['สอบจำลอง', 'ข้อสอบ']) and 'สอบ' in user_message_lower:
                result = handle_start_exam_command(user_id, user_message, gemini_client_primary, gemini_model_primary, db)
                
                if "✅" in result:
                    time.sleep(1)
                    first_q = handle_show_current_question(user_id, db)
                    reply_to_line(event.reply_token, [TextMessage(text=result), TextMessage(text=first_q)])
                    return
                else:
                    reply_message = TextMessage(text=result)
            
            elif 'ยกเลิกสอบ' in user_message_lower:
                reply_message = TextMessage(text=handle_cancel_exam(user_id, db))
            
            elif 'เฉลยข้อสอบ' in user_message_lower:
                reply_message = TextMessage(text=handle_show_explanation(user_id, db))
            
            elif 'สถิติสอบ' in user_message_lower:
                reply_message = TextMessage(text=handle_exam_stats(user_id, db))
        
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"Exam simulator error: {e}")
    
    # ========================================================================
    # 🍔 FOOD RANDOMIZER
    # ========================================================================
    if not reply_message and any(kw in user_message_lower for kw in ['กินอะไรดี', 'กินไร', 'แนะนำอาหาร']):
        try:
            from food_randomizer import handle_food_randomizer_command
            reply_message = handle_food_randomizer_command(user_message)
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"Food randomizer error: {e}")
    
    # ========================================================================
    # HOMEWORK COMMANDS
    # ========================================================================
    if not reply_message and user_message.startswith("สั่งการบ้าน"):
        reply_message = _handle_add_homework(user_message)
    
    elif not reply_message and user_message in ["การบ้าน", "ดูการบ้าน"]:
        reply_message = TextMessage(text=get_homeworks_from_db())
    
    elif not reply_message and user_message in ["ลบการบ้านทั้งหมด"]:
        reply_message = TextMessage(text=clear_homework_db())
    
    # ========================================================================
    # CALCULATOR & GRADE CALCULATOR
    # ========================================================================
    if not reply_message and any(kw in user_message_lower for kw in ['คำนวณ', 'คิด']):
        if 'เกรด' in user_message_lower or 'gpa' in user_message_lower:
            reply_message = get_grade_calculator_response(user_message, user_id)
        else:
            reply_message = get_calculator_response(user_message)
    
    # ========================================================================
    # STANDARD COMMANDS
    # ========================================================================
    if not reply_message:
        for keywords, action in COMMANDS:
            matched = False
            for keyword in keywords:
                if keyword.lower() in user_message_lower:
                    try:
                        reply_message = action(user_message) if action.__code__.co_argcount > 0 else action()
                        matched = True
                        break
                    except Exception as e:
                        logger.exception(f"Error: {e}")
                        reply_message = TextMessage(text=MESSAGES["ACTION_ERROR"])
                        break
            if matched:
                break
    
    # ========================================================================
    # FALLBACK TO AI
    # ========================================================================
    if not reply_message:
        try:
            ai_text = get_gemini_response(user_message)
            reply_message = TextMessage(text=ai_text)
        except Exception as e:
            logger.exception(f"AI error: {e}")
            reply_message = TextMessage(text=MESSAGES["AI_ERROR"])
    
    # Send reply
    try:
        if reply_message:
            reply_to_line(event.reply_token, [reply_message])
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
            
            if not subject or not detail:
                return TextMessage(text="⚠️ กรุณาระบุข้อมูลให้ครบ")
            
            result = add_homework_to_db(subject, detail, due)
            return TextMessage(text=result)
    
    return TextMessage(text="⚠️ รูปแบบ: สั่งการบ้าน | วิชา | รายละเอียด | วันส่ง")

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'handler',
    'handle_follow',
    'handle_message',
    'reply_to_line',
]
