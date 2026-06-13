# -*- coding: utf-8 -*-
"""
MTC Assistant - Handlers Module (IMPROVED UX Edition)
"""

import threading
from typing import List, Optional, Union
from flask import request

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, 
    TextMessage, ImageMessage, FlexMessage
)
from linebot.v3.webhooks import (
    AudioMessageContent,
    FileMessageContent,
    FollowEvent,
    ImageMessageContent,
    LocationMessageContent,
    MessageEvent,
    StickerMessageContent,
    TextMessageContent,
    VideoMessageContent,
)

# Import from config
from mtc_assistant.config import (
    logger, ACCESS_TOKEN, CHANNEL_SECRET, MESSAGES,
    ADMIN_USER_IDS
)

# Import from features
from mtc_assistant.features import (
    get_gemini_response,
    get_homeworks_from_db, clear_homework_db,
    get_calculator_response, get_grade_calculator_response,
    get_help_message,
)

# Import features module to access db
import mtc_assistant.features as features

# Import broadcast functions
import mtc_assistant.broadcast as broadcast

from mtc_assistant.admin_router import handle_admin_command
from mtc_assistant.ai_entry_router import (
    AIEntryKind,
    UNKNOWN_MESSAGE_TEXT,
    classify_ai_entry,
)
from mtc_assistant.ai_runtime import generate_ai_response
from mtc_assistant.class_context import onboarding_prompt, resolve_line_class_context
from mtc_assistant.command_router import handle_standard_command
from mtc_assistant.constants import (
    HOMEWORK_START_COMMANDS,
    HOMEWORK_CANCEL_COMMANDS,
    HOMEWORK_VIEW_COMMANDS,
)
from mtc_assistant.homework_session import (
    HomeworkSessionStoreReadError,
    has_homework_session,
    start_homework_session,
    handle_homework_session,
    cancel_homework_session,
    session_read_failure_message,
)
from mtc_assistant.rate_limit import is_rate_limited
from mtc_assistant.invite_codes import is_join_command, join_class_with_invite
from mtc_assistant.quick_replies import build_unknown_message_quick_reply

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
             "พิมพ์ JOIN <code> หรือ เข้าห้อง <code> เพื่อเข้าห้องของตัวเอง\n"
             "ถ้าไม่มีโค้ด ให้ติดต่อแอดมินห้อง"
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
    
    logged_message = "[join command redacted]" if is_join_command(user_message) else user_message[:100]
    logger.info("Message from %s: %s", user_id, logged_message)
    
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
    
    # Check rate limit
    if is_rate_limited(user_id):
        reply_to_line(event.reply_token, [TextMessage(
            text="ใจเย็นๆ น้า พิมพ์รัวไปนิดนึง รอแป๊บนะ"
        )])
        return
    
    user_message_lower = user_message.lower()
    reply_message = None
    db = features.db

    # ========================================================================
    # CLASS ONBOARDING
    # ========================================================================
    if is_join_command(user_message):
        result = join_class_with_invite(db, user_id, user_message)
        reply_to_line(event.reply_token, [TextMessage(text=result.message)])
        return

    class_context = resolve_line_class_context(db, user_id)
    if class_context is None:
        if user_message_lower in ("help", "ช่วยเหลือ", "คำสั่ง"):
            reply_to_line(event.reply_token, [get_help_message(user_message)])
            return
        reply_to_line(event.reply_token, [TextMessage(text=onboarding_prompt())])
        return

    # Track user for broadcast & impersonate after class resolution so brand-new
    # users are not mistaken for legacy MTC12 users during migration.
    try:
        broadcast.track_user(user_id, class_context=class_context)

        try:
            from mtc_assistant.admin_impersonate import track_user_activity
            track_user_activity(user_id)
        except ImportError:
            pass
    except Exception as e:
        logger.error(f"Failed to track user: {e}")
    
    # ========================================================================
    # INTERACTIVE HOMEWORK SYSTEM
    # ========================================================================
    
    # Cancel homework session
    if user_message in HOMEWORK_CANCEL_COMMANDS:
        result = cancel_homework_session(user_id, db=db) or "ไม่มี session การบ้านที่จะยกเลิก"
        reply_to_line(event.reply_token, [TextMessage(text=result)])
        return
    
    # Handle homework session steps
    try:
        active_homework_session = has_homework_session(user_id, db=db)
    except HomeworkSessionStoreReadError:
        reply_to_line(event.reply_token, [session_read_failure_message()])
        return

    if active_homework_session:
        result = handle_homework_session(user_id, user_message, db=db, class_context=class_context)
        if result:
            reply_to_line(event.reply_token, [result])
            return

    # Start homework session
    if user_message in HOMEWORK_START_COMMANDS:
        message, quick_reply = start_homework_session(user_id, class_context=class_context, db=db)
        reply_to_line(event.reply_token, [message])
        return
    
    # View homework
    if user_message in HOMEWORK_VIEW_COMMANDS:
        hw_text = get_homeworks_from_db(class_context)
        reply_to_line(event.reply_token, [TextMessage(text=hw_text)])
        return

    explicit_ai = classify_ai_entry(user_message)
    if explicit_ai.kind == AIEntryKind.EMPTY_AI:
        reply_to_line(event.reply_token, [TextMessage(text=explicit_ai.response_text)])
        return
    if explicit_ai.kind == AIEntryKind.EXPLICIT_AI:
        try:
            ai_text = generate_ai_response(
                explicit_ai.prompt,
                class_id=class_context.class_id,
                user_id=user_id,
                db=features.db,
                legacy_responder=get_gemini_response,
            )
        except Exception as e:
            logger.exception("Explicit AI error: %s", e)
            ai_text = "AI ของเรากำลังมึนตึ้บ ขอเวลาตั้งสติแป๊บนึงนะ 😵‍💫 ลองทักมาใหม่นะครับ!"
        reply_to_line(event.reply_token, [TextMessage(text=ai_text)])
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
            from mtc_assistant.food_randomizer import handle_food_randomizer_command
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
            reply_message = get_calculator_response(user_message, user_id)
    
    # ========================================================================
    # STANDARD COMMANDS
    # ========================================================================
    if not reply_message:
        reply_message = handle_standard_command(user_message, user_message_lower, class_context=class_context)
    
    # ========================================================================
    # SMART AI ENTRY OR UNKNOWN HELPER
    # ========================================================================
    if not reply_message:
        ai_entry = classify_ai_entry(user_message)
        if ai_entry.kind in (AIEntryKind.DATE_UTILITY, AIEntryKind.CLASSROOM_BRIDGE):
            reply_message = TextMessage(text=ai_entry.response_text)
        elif ai_entry.kind == AIEntryKind.NATURAL_AI:
            try:
                ai_text = generate_ai_response(
                    ai_entry.prompt,
                    class_id=class_context.class_id,
                    user_id=user_id,
                    db=features.db,
                    legacy_responder=get_gemini_response,
                )
                reply_message = TextMessage(text=ai_text)
            except Exception as e:
                logger.exception("Natural AI error: %s", e)
                reply_message = TextMessage(
                    text="AI ของเรากำลังมึนตึ้บ ขอเวลาตั้งสติแป๊บนึงนะ 😵‍💫 ลองทักมาใหม่นะครับ!"
                )
        else:
            reply_message = TextMessage(
                text=UNKNOWN_MESSAGE_TEXT,
                quick_reply=build_unknown_message_quick_reply(),
            )
    
    # Send reply
    try:
        if reply_message:
            reply_to_line(event.reply_token, [reply_message])
    except Exception as e:
        logger.exception(f"Failed to send reply: {e}")

@handler.add(MessageEvent, message=AudioMessageContent) if handler else (lambda f: f)
@handler.add(MessageEvent, message=FileMessageContent) if handler else (lambda f: f)
@handler.add(MessageEvent, message=ImageMessageContent) if handler else (lambda f: f)
@handler.add(MessageEvent, message=LocationMessageContent) if handler else (lambda f: f)
@handler.add(MessageEvent, message=StickerMessageContent) if handler else (lambda f: f)
@handler.add(MessageEvent, message=VideoMessageContent) if handler else (lambda f: f)
def handle_non_text_message(event):
    """Reply safely to supported non-text LINE payloads."""
    message_type = getattr(getattr(event, "message", None), "type", "unknown")
    logger.info("Unsupported non-text LINE message received: %s", message_type)
    reply_to_line(event.reply_token, [TextMessage(
        text=(
            "ตอนนี้บอทรองรับคำสั่งแบบข้อความเป็นหลัก\n"
            "หากต้องการใช้ Paperless Capture AI ให้เปิดผ่าน Dashboard ผู้ดูแลระบบก่อน"
        )
    )])

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'handler',
    'handle_follow',
    'handle_message',
    'handle_non_text_message',
    'reply_to_line',
]
