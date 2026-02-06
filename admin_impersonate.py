# -*- coding: utf-8 -*-
"""
MTC Assistant - Admin Impersonate Feature
ฟีเจอร์สำหรับแอดมินส่งข้อความไปหาผู้ใช้โดยตรง (สำหรับแกล้งเพื่อน 😄)

Usage:
    1. พิมพ์ "ดูผู้ใช้" → ดูรายชื่อผู้ใช้ล่าสุด
    2. พิมพ์ "ส่งถึง [user_id] [ข้อความ]" → ส่งข้อความแกล้งเพื่อน
    3. พิมพ์ "ยกเลิกส่ง" → ยกเลิก

Example:
    ส่งถึง U1234567890 สวัสดีครับ ผมเป็น AI ที่ฉลาดมาก
"""

import time
from typing import Dict, Optional, Tuple
from config import logger, ADMIN_USER_IDS
from linebot.v3.messaging import (
    ApiClient, MessagingApi, Configuration,
    PushMessageRequest, TextMessage
)

# ============================================================================
# GLOBAL STATE (Session Management)
# ============================================================================

# Store active impersonate sessions: {admin_id: {"target": user_id, "started_at": timestamp}}
_impersonate_sessions: Dict[str, Dict] = {}

# Store recent users list for easy selection
_recent_users_cache: Dict[str, Dict] = {}

# LINE API client
_line_api = None

# ============================================================================
# INITIALIZATION
# ============================================================================

def set_line_api(config: Configuration):
    """Set LINE API for sending messages"""
    global _line_api
    if config:
        _line_api = MessagingApi(ApiClient(config))
        logger.info("✅ Impersonate feature initialized")

# ============================================================================
# USER TRACKING (for easy selection)
# ============================================================================

def track_user_activity(user_id: str, display_name: str = "Unknown"):
    """
    Track user activity for the recent users list
    Called automatically when users send messages
    """
    global _recent_users_cache
    
    _recent_users_cache[user_id] = {
        "user_id": user_id,
        "display_name": display_name,
        "last_seen": time.time(),
        "last_seen_str": time.strftime("%d/%m/%Y %H:%M")
    }
    
    # Keep only last 20 users
    if len(_recent_users_cache) > 20:
        # Sort by last_seen and keep newest 20
        sorted_users = sorted(
            _recent_users_cache.items(),
            key=lambda x: x[1]["last_seen"],
            reverse=True
        )
        _recent_users_cache = dict(sorted_users[:20])

# ============================================================================
# CORE FUNCTIONS
# ============================================================================

def send_impersonate_message(target_user_id: str, message: str) -> Tuple[bool, str]:
    """
    Send a custom message to specific user (as if bot is talking)
    
    Args:
        target_user_id: LINE User ID to send to
        message: Custom message to send
    
    Returns:
        (success, result_message)
    """
    if not _line_api:
        return False, "❌ LINE API ไม่พร้อมใช้งาน"
    
    try:
        _line_api.push_message(
            PushMessageRequest(
                to=target_user_id,
                messages=[TextMessage(text=message)]
            )
        )
        logger.info(f"📤 Impersonate message sent to {target_user_id}")
        return True, f"✅ ส่งข้อความสำเร็จถึง {target_user_id[:8]}..."
    
    except Exception as e:
        logger.error(f"Failed to send impersonate message: {e}")
        return False, f"❌ ส่งข้อความล้มเหลว: {str(e)}"

# ============================================================================
# COMMAND HANDLERS
# ============================================================================

def handle_list_users_command(admin_id: str) -> str:
    """
    Handle: ดูผู้ใช้
    Show list of recent users for easy selection
    """
    if not _recent_users_cache:
        return (
            "📋 *ผู้ใช้ล่าสุด*\n\n"
            "⚠️ ยังไม่มีผู้ใช้ในระบบ\n"
            "รอให้มีคนส่งข้อความก่อนนะครับ"
        )
    
    message = f"📋 *ผู้ใช้ล่าสุด* ({len(_recent_users_cache)} คน)\n\n"
    
    # Sort by last seen (newest first)
    sorted_users = sorted(
        _recent_users_cache.items(),
        key=lambda x: x[1]["last_seen"],
        reverse=True
    )
    
    for i, (user_id, info) in enumerate(sorted_users[:10], 1):
        # Truncate user_id for display
        short_id = user_id[:12] + "..."
        message += f"{i}. `{short_id}`\n"
        message += f"   เห็นล่าสุด: {info['last_seen_str']}\n\n"
    
    if len(sorted_users) > 10:
        message += f"... และอีก {len(sorted_users) - 10} คน\n\n"
    
    message += (
        "💡 *วิธีส่งข้อความ:*\n"
        "ส่งถึง [user_id] [ข้อความ]\n\n"
        "📌 *ตัวอย่าง:*\n"
        f"ส่งถึง {sorted_users[0][0][:15]} สวัสดีครับ"
    )
    
    return message

def handle_send_impersonate_command(admin_id: str, user_message: str) -> str:
    """
    Handle: ส่งถึง [user_id] [message]
    Send custom message to specific user
    """
    # Parse command
    parts = user_message.split(maxsplit=2)
    
    if len(parts) < 3:
        return (
            "⚠️ *รูปแบบคำสั่ง:*\n"
            "ส่งถึง [user_id] [ข้อความ]\n\n"
            "📌 *ตัวอย่าง:*\n"
            "ส่งถึง U1234567890 สวัสดีครับผม\n\n"
            "💡 พิมพ์ 'ดูผู้ใช้' เพื่อดูรายชื่อ"
        )
    
    target_user_id = parts[1]
    message = parts[2]
    
    # Validate user_id format (basic check)
    if not target_user_id.startswith("U") or len(target_user_id) < 10:
        return (
            "❌ User ID ไม่ถูกต้อง\n\n"
            "User ID ต้องเริ่มด้วย 'U' และมีความยาวอย่างน้อย 33 ตัวอักษร\n\n"
            "💡 พิมพ์ 'ดูผู้ใช้' เพื่อดู User ID ที่ถูกต้อง"
        )
    
    # Prevent sending to admin themselves (accidental self-prank)
    if target_user_id == admin_id:
        return "😅 ไม่สามารถส่งข้อความหาตัวเองได้ครับ"
    
    # Prevent sending to other admins
    if target_user_id in ADMIN_USER_IDS:
        return "🚫 ไม่สามารถส่งข้อความหา Admin คนอื่นได้"
    
    # Send the message
    success, result = send_impersonate_message(target_user_id, message)
    
    if success:
        # Log the activity
        logger.warning(
            f"🎭 IMPERSONATE: Admin {admin_id[:8]} sent message to {target_user_id[:8]}: "
            f"{message[:50]}"
        )
        
        return (
            f"{result}\n\n"
            f"📨 *ข้อความที่ส่ง:*\n"
            f"{message[:200]}\n\n"
            f"🎭 ผู้ใช้จะเห็นข้อความนี้เหมือนบอทพูดเอง\n"
            f"⏰ เวลา: {time.strftime('%H:%M:%S')}"
        )
    else:
        return result

def handle_test_impersonate_command(admin_id: str, user_message: str) -> str:
    """
    Handle: ทดสอบส่ง [message]
    Send test message to admin themselves (for testing)
    """
    parts = user_message.split(maxsplit=1)
    
    if len(parts) < 2:
        return (
            "⚠️ *รูปแบบคำสั่ง:*\n"
            "ทดสอบส่ง [ข้อความ]\n\n"
            "📌 *ตัวอย่าง:*\n"
            "ทดสอบส่ง สวัสดีครับ ผมเป็น AI"
        )
    
    message = parts[1]
    
    # Send to admin themselves
    success, result = send_impersonate_message(admin_id, message)
    
    if success:
        return (
            "✅ ส่งข้อความทดสอบแล้ว!\n\n"
            "คุณควรเห็นข้อความนี้ในแชทส่วนตัว:\n"
            f'"{message[:100]}"\n\n'
            "💡 ถ้าได้รับแล้ว แสดงว่าระบบทำงานปกติ"
        )
    else:
        return result

def get_impersonate_help() -> str:
    """Get help text for impersonate commands"""
    return """
🎭 *ส่งข้อความหาผู้ใช้*

• ดูผู้ใช้
  → ดูรายชื่อผู้ใช้ล่าสุด

• ส่งถึง [user_id] [ข้อความ]
  → ส่งข้อความไปหาผู้ใช้ที่เลือก
  
• ทดสอบส่ง [ข้อความ]
  → ส่งข้อความทดสอบหาตัวเอง

⚠️ *หมายเหตุ:*
- ใช้เพื่อความสนุกเท่านั้น
- อย่าส่งข้อความที่ไม่เหมาะสม
- ผู้ใช้จะเห็นเหมือนบอทพูดเอง
"""

# ============================================================================
# INTEGRATION HELPER
# ============================================================================

def get_impersonate_commands():
    """
    Return command tuples for integration with handlers.py
    
    Usage in handlers.py:
        from admin_impersonate import get_impersonate_commands, track_user_activity
        
        # In handle_message, track all users:
        track_user_activity(user_id, display_name)
        
        # In admin commands section:
        for keywords, handler in get_impersonate_commands():
            if matches:
                reply = handler(user_id, user_message)
    """
    return [
        (("ดูผู้ใช้", "users list", "รายชื่อผู้ใช้"), 
         lambda admin_id, msg: handle_list_users_command(admin_id)),
        
        (("ส่งถึง", "send to"), 
         lambda admin_id, msg: handle_send_impersonate_command(admin_id, msg)),
        
        (("ทดสอบส่ง", "test send"), 
         lambda admin_id, msg: handle_test_impersonate_command(admin_id, msg)),
    ]

# ============================================================================
# SAFETY & LOGGING
# ============================================================================

def log_impersonate_activity(admin_id: str, target_id: str, message: str):
    """Log all impersonate activities for audit trail"""
    logger.warning(
        f"🎭 IMPERSONATE LOG: "
        f"Admin={admin_id[:8]} → Target={target_id[:8]} | "
        f"Message={message[:100]}"
    )

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'set_line_api',
    'track_user_activity',
    'send_impersonate_message',
    'get_impersonate_commands',
    'get_impersonate_help',
    'handle_list_users_command',
    'handle_send_impersonate_command',
    'handle_test_impersonate_command',
]
