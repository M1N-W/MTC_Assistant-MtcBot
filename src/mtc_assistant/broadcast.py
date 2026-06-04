# -*- coding: utf-8 -*-
"""
MTC Assistant - Broadcast Module
ระบบประกาศ Push สำหรับส่งข้อความไปหาผู้ใช้ทั้งหมด
"""

import datetime  # FIXED: Added missing import for broadcast_homework_reminder
import time

try:  # pragma: no cover
    from linebot.v3.messaging import (
        ApiClient, MessagingApi, Configuration,
        TextMessage, PushMessageRequest
    )
except Exception:  # fallback for static analysis or missing package
    # Provide minimal stubs so linters/type-checkers won't fail.
    ApiClient = object  # type: ignore
    MessagingApi = object  # type: ignore
    Configuration = object  # type: ignore
    TextMessage = object  # type: ignore
    PushMessageRequest = object  # type: ignore
from mtc_assistant.config import logger
from firebase_admin import firestore
from mtc_assistant.firestore_paths import class_collection

# Global variables with memory management
db = None
line_api = None
_tracked_users_cache: set = set()  # in-memory cache of already-seen user IDs
_cache_max_size = 10000  # Maximum cache size to prevent memory issues
_firebase_unavailable_warned = False  # log "Firebase unavailable" only once per process

def cleanup_user_cache():
    """Clean up user cache to prevent memory leaks"""
    global _tracked_users_cache
    if len(_tracked_users_cache) > _cache_max_size:
        # Remove oldest half of the cache
        cache_list = list(_tracked_users_cache)
        _tracked_users_cache = set(cache_list[_cache_max_size//2:])
        logger.info(f"Cleaned user cache, size now: {len(_tracked_users_cache)}")

# ============================================================================
# INITIALIZATION
# ============================================================================

def set_database(database):
    """Set Firebase database instance"""
    global db
    db = database

def set_line_api(config: Configuration):
    """Initialize LINE Messaging API"""
    global line_api
    if config:
        line_api = MessagingApi(ApiClient(config))

# ============================================================================
# USER TRACKING
# ============================================================================

def track_user(user_id: str, display_name: str = "Unknown", class_context=None):
    """
    บันทึก user_id เข้า Firebase เพื่อส่ง broadcast
    เรียกฟังก์ชันนี้ทุกครั้งที่มีคนส่งข้อความ
    """
    global _firebase_unavailable_warned
    if not db:
        if not _firebase_unavailable_warned:
            logger.warning(
                "Firebase not yet available for user tracking — "
                "messages will still be answered, but user data won't be persisted "
                "until the Firebase connection is established. "
                "(further occurrences logged at DEBUG)"
            )
            _firebase_unavailable_warned = True
        else:
            logger.debug("Firebase not available for user tracking (suppressed)")
        return False

    try:
        is_new_user = user_id not in _tracked_users_cache
        _tracked_users_cache.add(user_id)
        
        # Clean cache if it gets too large
        cleanup_user_cache()

        active_class_id = getattr(class_context, "class_id", None)
        root_payload = {
            'user_id': user_id,
            'display_name': display_name,
            'last_seen': firestore.SERVER_TIMESTAMP,
            'is_active': True,
        }
        if active_class_id:
            root_payload.update({
                'active_class_id': active_class_id,
                'class_ids': firestore.ArrayUnion([active_class_id]),
                'status': 'active',
                'last_seen_at': firestore.SERVER_TIMESTAMP,
            })

        db.collection('users').document(user_id).set(root_payload, merge=True)

        if active_class_id and not getattr(class_context, "is_legacy_fallback", False):
            class_collection(db, active_class_id, "users").document(user_id).set({
                'user_id': user_id,
                'display_name': display_name,
                'role': getattr(class_context, "role", "student"),
                'status': 'active',
                'last_seen_at': firestore.SERVER_TIMESTAMP,
            }, merge=True)

        if is_new_user:
            db.collection('meta').document('stats').set(
                {'user_count': firestore.Increment(1)},
                merge=True,
            )

        logger.debug(f"User tracked: {user_id} (new={is_new_user})")
        return True
    except Exception as e:
        logger.error(f"Error tracking user: {e}")
        return False

def get_all_users():
    """ดึงรายชื่อ user_id ทั้งหมดจาก Firebase"""
    if not db:
        logger.warning("Firebase not available for user list; returning an empty user list")
        return []
    
    try:
        users_ref = db.collection('users').where('is_active', '==', True).stream()
        user_ids = [u.to_dict().get('user_id') for u in users_ref]
        user_ids = [uid for uid in user_ids if uid]
        logger.info(f"Retrieved {len(user_ids)} active users")
        return user_ids
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return []

def get_user_count() -> int:
    """
    นับจำนวนผู้ใช้ทั้งหมด

    Reads a single counter document instead of streaming the entire users
    collection — O(1) Firestore reads regardless of how many users exist.
    The counter is incremented by track_user() the first time each user appears.
    """
    if not db:
        return 0
    try:
        doc = db.collection('meta').document('stats').get()
        if doc.exists:
            return doc.to_dict().get('user_count', 0)
        return 0
    except Exception as e:
        logger.error(f"Error getting user count: {e}")
        return 0

# ============================================================================
# INTERNAL HELPERS
# ============================================================================

def _push_with_retry(user_id: str, message_text: str, max_retries: int = 3) -> bool:
    """
    Send a single push message with exponential-backoff retry.

    Retries only on LINE rate-limit (HTTP 429) errors.  All other errors are
    treated as non-retryable to avoid hammering the API on permanent failures.

    Returns:
        True if the message was delivered successfully.
    """
    for attempt in range(max_retries):
        try:
            line_api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=message_text)]
                )
            )
            return True
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "Too Many Requests" in err_str.lower():
                wait = 2 ** attempt   # 1 s → 2 s → 4 s
                logger.warning(
                    f"⚠️ Rate-limited by LINE API. "
                    f"Waiting {wait}s before retry {attempt + 1}/{max_retries}…"
                )
                time.sleep(wait)
            else:
                # Non-retryable (bad user_id, auth error, etc.)
                logger.error(f"❌ Non-retryable error sending to {user_id}: {e}")
                return False
    logger.error(f"❌ Gave up sending to {user_id} after {max_retries} attempts")
    return False




def broadcast_message(message_text: str) -> dict:
    """
    ส่งข้อความไปหาผู้ใช้ทั้งหมด
    
    Returns:
        dict: {"success": bool, "sent_count": int, "failed_count": int, "message": str}
    """
    if not line_api:
        return {
            "success": False,
            "sent_count": 0,
            "failed_count": 0,
            "message": "LINE API not configured"
        }
    
    user_ids = get_all_users()
    
    if not user_ids:
        return {
            "success": False,
            "sent_count": 0,
            "failed_count": 0,
            "message": "No users found"
        }
    
    sent_count = 0
    failed_count = 0

    for i, user_id in enumerate(user_ids):
        if _push_with_retry(user_id, message_text):
            sent_count += 1
            logger.debug(f"Message sent to {user_id}")
        else:
            failed_count += 1

        # Throttle: pause briefly every 10 messages to stay within
        # LINE's soft push-message rate limit (~500 req/min).
        if i > 0 and i % 10 == 0:
            time.sleep(0.2)
    
    result_message = f"✅ ผลการส่งประกาศ\n\nส่งสำเร็จ: {sent_count} คน"
    if failed_count > 0:
        result_message += f"\nส่งไม่สำเร็จ: {failed_count} คน"
    
    return {
        "success": sent_count > 0,
        "sent_count": sent_count,
        "failed_count": failed_count,
        "message": result_message
    }

def broadcast_homework_reminder():
    """
    แจ้งเตือนการบ้านอัตโนมัติ
    เรียกใช้โดย scheduler (เช่น ทุกวันเวลา 20:00)
    """
    if not db:
        logger.error("Firebase not available for homework reminder")
        return
    
    try:
        # ดึงการบ้านที่ต้องส่งพรุ่งนี้
        # FIXED: Now datetime is properly imported
        tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        homeworks = db.collection('homeworks').where('due_date', '==', tomorrow).stream()
        hw_list = []
        
        for hw in homeworks:
            data = hw.to_dict()
            hw_list.append(f"• {data.get('subject')}: {data.get('detail')}")
        
        if hw_list:
            message = (
                "ประกาศจากระบบหัวหน้าห้อง! 📢✨\n\n"
                "พรุ่งนี้พวกเรามีการบ้านต้องส่งน้า:\n" +
                "\n".join(hw_list) +
                "\n\nใครยังไม่เริ่ม ปั่นด่วนๆ เลยนะคืนนี้ สู้ๆ! ✌️🔥"
            )
            
            result = broadcast_message(message)
            logger.info(f"Homework reminder sent: {result}")
    except Exception as e:
        logger.error(f"Error sending homework reminder: {e}")

# ============================================================================
# BROADCAST TEMPLATES
# ============================================================================

def create_announcement(title: str, content: str, emoji: str = "📢") -> str:
    """สร้างข้อความประกาศ"""
    return f"{emoji} *{title}*\n\n{content}\n\n— MTC Assistant"

def create_reminder(subject: str, details: str) -> str:
    """สร้างข้อความเตือนความจำ"""
    return f"⏰ เตือนความจำ: {subject}\n\n{details}"

def create_urgent_alert(message: str) -> str:
    """สร้างข้อความด่วน"""
    return f"🚨 *ด่วน!* 🚨\n\n{message}"

# ============================================================================
# ADMIN HELPERS
# ============================================================================

def save_broadcast_history(admin_id: str, message: str, result: dict):
    """บันทึกประวัติการส่ง broadcast"""
    if not db:
        return
    
    try:
        db.collection('broadcast_history').add({
            'admin_id': admin_id,
            'message': message,
            'sent_count': result.get('sent_count', 0),
            'failed_count': result.get('failed_count', 0),
            'timestamp': firestore.SERVER_TIMESTAMP,
            'success': result.get('success', False)
        })
        logger.info(f"Broadcast history saved by {admin_id}")
    except Exception as e:
        logger.error(f"Error saving broadcast history: {e}")

def get_broadcast_stats() -> str:
    """ดูสถิติการส่ง broadcast"""
    if not db:
        return "ยังไม่สามารถดึงรายงานการส่งประกาศได้\nสถานะ: ฐานข้อมูลยังไม่พร้อม"
    
    try:
        # นับจำนวนครั้งที่ส่ง
        history = db.collection('broadcast_history').order_by(
            'timestamp', direction=firestore.Query.DESCENDING
        ).limit(10).stream()
        
        total_broadcasts = 0
        total_sent = 0
        recent_broadcasts = []
        
        for doc in history:
            data = doc.to_dict()
            total_broadcasts += 1
            total_sent += data.get('sent_count', 0)
            
            timestamp = data.get('timestamp')
            try:
                time_str = timestamp.strftime("%d/%m %H:%M") if hasattr(timestamp, 'strftime') else "N/A"
            except Exception:
                time_str = "N/A"
            
            recent_broadcasts.append(
                f"• {time_str} - ส่ง {data.get('sent_count', 0)} คน"
            )
        
        user_count = get_user_count()
        
        # Resolve the ternary BEFORE building the stats string.
        # Inlining it caused Python's operator precedence to bind the entire
        # left-hand f-string to the conditional, silently discarding all
        # counters/headers when recent_broadcasts was empty.
        history_text = (
            "\n".join(recent_broadcasts[:5])
            if recent_broadcasts
            else "ยังไม่มีประวัติการส่งประกาศ"
        )

        stats = (
            f"รายงานการส่งประกาศ\n\n"
            f"จำนวนผู้ใช้: {user_count} คน\n"
            f"จำนวนครั้งที่ส่งประกาศ: {total_broadcasts} ครั้ง\n"
            f"✅ ส่งข้อความแล้ว: {total_sent} ข้อความ\n\n"
            f"ประวัติการส่งล่าสุด:\n"
            f"{history_text}"
        )
        
        return stats
    except Exception as e:
        logger.error(f"Error getting broadcast stats: {e}")
        return f"ดึงรายงานการส่งประกาศไม่สำเร็จ\nสาเหตุ: {str(e)}"

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'set_database',
    'set_line_api',
    'track_user',
    'get_all_users',
    'get_user_count',
    'broadcast_message',
    'broadcast_homework_reminder',
    'create_announcement',
    'create_reminder',
    'create_urgent_alert',
    'save_broadcast_history',
    'get_broadcast_stats',
]
