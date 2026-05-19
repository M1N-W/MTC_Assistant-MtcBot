# -*- coding: utf-8 -*-
"""
MTC Assistant - Handlers Module (IMPROVED UX Edition)
"""

import threading
from typing import Dict, List, Optional, Union
from flask import request

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, 
    TextMessage, ImageMessage, FlexMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

# Import from config
from mtc_assistant.config import (
    logger, ACCESS_TOKEN, CHANNEL_SECRET, MESSAGES,
    ADMIN_USER_IDS
)

# Import from features
from mtc_assistant.features import (
    get_worksheet_message, get_school_link_message, get_timetable_image_message,
    get_grade_link_message, get_absence_form_message, get_bio_link_message,
    get_physic_link_message, get_help_message, get_next_class_message,
    get_time_until_next_class_message, get_exam_countdown_message,
    get_music_link_message, get_gemini_response,
    get_homeworks_from_db, clear_homework_db,
    get_calculator_response, get_grade_calculator_response
)

# Import features module to access db
import mtc_assistant.features as features

# Import broadcast functions
import mtc_assistant.broadcast as broadcast

from mtc_assistant.admin_router import handle_admin_command
from mtc_assistant.constants import (
    HOMEWORK_START_COMMANDS,
    HOMEWORK_CANCEL_COMMANDS,
    HOMEWORK_VIEW_COMMANDS,
)
from mtc_assistant.flex_messages import get_links_menu_message
from mtc_assistant.homework_session import (
    has_homework_session,
    start_homework_session,
    handle_homework_session,
    cancel_homework_session,
)
from mtc_assistant.rate_limit import is_rate_limited

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
# MESSAGE FORMAT HELPERS
# ============================================================================

def format_success_message(title: str, details: List[str]) -> str:
    """Format a success message"""
    message = f"{title}\n\n"
    for detail in details:
        message += f"  {detail}\n"
    return message

def format_info_message(title: str, items: Dict[str, str]) -> str:
    """Format an informative message"""
    message = f"{title}\n\n"
    for key, value in items.items():
        message += f"{key}: {value}\n"
    return message

def format_error_message(error: str, suggestion: str = None) -> str:
    """Format an error message with optional suggestion"""
    message = f"{error}\n"
    if suggestion:
        message += f"\n{suggestion}"
    return message

# ============================================================================
# COMMANDS LIST
# ============================================================================

COMMANDS = [
    (("ตารางเรียน", "ตารางสอน"), get_timetable_image_message),
    (("เช็คเวลาเรียน", "เช็คเวลา"), get_time_until_next_class_message),
    (("ดูงาน",), lambda msg: TextMessage(text=get_homeworks_from_db())),
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
    welcome_message = TextMessage(
        text="ยินดีต้อนรับสู่ MTC Assistant\n\n"
             "บอทช่วยงานห้อง MTC สร้างโดยนักเรียน MTC12\n\n"
             "พิมพ์ 'help' เพื่อดูคำสั่งทั้งหมด\n"
             "หรือถามอะไรก็ได้เลย"
    )
    try:
        reply_to_line(event.reply_token, [welcome_message])
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
    
    # ========================================================================
    # CHECK BLACKLIST (CRITICAL - FIRST CHECK!)
    # ========================================================================
    try:
        from mtc_assistant.user_blacklist import check_user_banned
        is_banned, ban_message = check_user_banned(user_id)
        if is_banned:
            reply_to_line(event.reply_token, [TextMessage(text=ban_message)])
            logger.warning(f"Banned user {user_id} attempted to use bot")
            return
    except ImportError:
        pass
    except Exception as e:
        logger.error(f"Blacklist check error: {e}")
    
    # Track user for broadcast & impersonate
    try:
        broadcast.track_user(user_id)
        
        try:
            from mtc_assistant.admin_impersonate import track_user_activity
            track_user_activity(user_id)
        except ImportError:
            pass
    except Exception as e:
        logger.error(f"Failed to track user: {e}")
    
    # Check rate limit
    if is_rate_limited(user_id):
        reply_to_line(event.reply_token, [TextMessage(
            text="ใจเย็นๆ น้า พิมพ์รัวไปนิดนึง รอแป๊บนะ"
        )])
        return
    
    user_message_lower = user_message.lower()
    reply_message = None
    
    # ========================================================================
    # INTERACTIVE HOMEWORK SYSTEM
    # ========================================================================
    
    # Start homework session
    if user_message in HOMEWORK_START_COMMANDS:
        message, quick_reply = start_homework_session(user_id)
        reply_to_line(event.reply_token, [message])
        return
    
    # Cancel homework session
    if user_message in HOMEWORK_CANCEL_COMMANDS:
        result = cancel_homework_session(user_id) or "ไม่มี session การบ้านที่จะยกเลิก"
        reply_to_line(event.reply_token, [TextMessage(text=result)])
        return
    
    # Handle homework session steps
    if has_homework_session(user_id):
        result = handle_homework_session(user_id, user_message)
        if result:
            reply_to_line(event.reply_token, [result])
            return
    
    # View homework
    if user_message in HOMEWORK_VIEW_COMMANDS:
        hw_text = get_homeworks_from_db()
        reply_to_line(event.reply_token, [TextMessage(text=hw_text)])
        return
    
    # ========================================================================
    # ADMIN COMMANDS
    # ========================================================================
    if user_id in ADMIN_USER_IDS:
        reply_message = handle_admin_command(user_id, user_message)
    
    # ========================================================================
    # EXAM SIMULATOR
    # ========================================================================
    if not reply_message:
        try:
            from mtc_assistant.exam_simulator import (
                get_session_manager,
                handle_start_exam_command,
                handle_answer_command,
                handle_show_current_question,
                handle_cancel_exam,
                handle_show_explanation,
                handle_exam_stats
            )
            
            db = features.db
            exam_mgr = get_session_manager(db)
            
            # Check if in exam session
            if exam_mgr.has_active_session(user_id):
                session = exam_mgr.get_session(user_id)
                exam_finished = session and session.current_index >= len(session.questions)

                # Answer question (only if exam not already finished)
                if not exam_finished and (user_message.strip().isdigit() or any(x in user_message_lower for x in ['ตอบ', 'คือ'])):
                    msg_text, send_next = handle_answer_command(user_id, user_message, db)

                    if msg_text and send_next:
                        next_q = handle_show_current_question(user_id, db)
                        reply_to_line(event.reply_token, [TextMessage(text=msg_text), TextMessage(text=next_q)])
                        return
                    elif msg_text:
                        reply_to_line(event.reply_token, [TextMessage(text=msg_text)])
                        return
            
            # Start exam
            if any(kw in user_message_lower for kw in ['สอบจำลอง', 'ข้อสอบ']) and 'สอบ' in user_message_lower:
                result = handle_start_exam_command(
                    user_id, 
                    user_message, 
                    features.gemini_client_primary, 
                    features.gemini_model_primary, 
                    db
                )
                
                if "✅" in result:
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
    # FOOD RANDOMIZER
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
                        reply_message = action(user_message)
                        matched = True
                        break
                    except Exception as e:
                        logger.exception(f"Error: {e}")
                        reply_message = TextMessage(
                            text=format_error_message(
                                "แงงง ระบบขัดข้องนิดหน่อยฮะ 🥺",
                                "ลองส่งคำสั่งมาใหม่อีกทีน้า"
                            )
                        )
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
            reply_message = TextMessage(
                text="AI ของเรากำลังมึนตึ้บ ขอเวลาตั้งสติแป๊บนึงนะ 😵‍💫 ลองทักมาใหม่นะครับ!"
            )
    
    # Send reply
    try:
        if reply_message:
            reply_to_line(event.reply_token, [reply_message])
    except Exception as e:
        logger.exception(f"Failed to send reply: {e}")

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'handler',
    'handle_follow',
    'handle_message',
    'reply_to_line',
]
