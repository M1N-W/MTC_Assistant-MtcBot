# -*- coding: utf-8 -*-
"""
MTC Assistant - Broadcast Module
ระบบประกาศ Push สำหรับส่งข้อความไปหาผู้ใช้ทั้งหมด
"""

import datetime  # FIXED: Added missing import for broadcast_homework_reminder

from linebot.v3.messaging import (
    ApiClient, MessagingApi, Configuration,
    BroadcastRequest, TextMessage, PushMessageRequest
)
from config import logger, ACCESS_TOKEN
from firebase_admin import firestore

# Global variables
db = None
line_api = None

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

def track_user(user_id: str, display_name: str = "Unknown"):
    """
    บันทึก user_id เข้า Firebase เพื่อส่ง broadcast
    เรียกฟังก์ชันนี้ทุกครั้งที่มีคนส่งข้อความ
    """
    if not db:
        logger.warning("Firebase not available for user tracking")
        return False
    
    try:
        user_ref = db.collection('users').document(user_id)
        user_ref.set({
            'user_id': user_id,
            'display_name': display_name,
            'last_seen': firestore.SERVER_TIMESTAMP,
            'is_active': True
        }, merge=True)
        logger.debug(f"User tracked: {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error tracking user: {e}")
        return False

def get_all_users():
    """ดึงรายชื่อ user_id ทั้งหมดจาก Firebase"""
    if not db:
        logger.error("Firebase not available")
        return []
    
    try:
        users_ref = db.collection('users').where('is_active', '==', True).stream()
        user_ids = [user.to_dict().get('user_id') for user in users_ref]
        logger.info(f"Retrieved {len(user_ids)} active users")
        return user_ids
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        return []

def get_user_count() -> int:
    """นับจำนวนผู้ใช้ทั้งหมด"""
    if not db:
        return 0
    
    try:
        users_ref = db.collection('users').where('is_active', '==', True).stream()
        count = sum(1 for _ in users_ref)
        return count
    except Exception as e:
        logger.error(f"Error counting users: {e}")
        return 0

# ============================================================================
# BROADCAST FUNCTIONS
# ============================================================================

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
    
    # ส่งข้อความไปทีละคน (เพราะ broadcast มี limit)
    for user_id in user_ids:
        try:
            line_api.push_message(
                PushMessageRequest(
                    to=user_id,
                    messages=[TextMessage(text=message_text)]
                )
            )
            sent_count += 1
            logger.debug(f"Message sent to {user_id}")
        except Exception as e:
            failed_count += 1
            logger.error(f"Failed to send to {user_id}: {e}")
    
    result_message = f"✅ ส่งสำเร็จ: {sent_count} คน"
    if failed_count > 0:
        result_message += f"\n❌ ล้มเหลว: {failed_count} คน"
    
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
                "⏰ 📢 เตือนความจำ!\n\n"
                "การบ้านที่ต้องส่งพรุ่งนี้:\n" +
                "\n".join(hw_list) +
                "\n\nอย่าลืมทำนะครับ! 💪"
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
        return "⚠️ ไม่สามารถดึงข้อมูลได้"
    
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
            if timestamp:
                time_str = timestamp.strftime("%d/%m %H:%M")
            else:
                time_str = "N/A"
            
            recent_broadcasts.append(
                f"• {time_str} - ส่ง {data.get('sent_count', 0)} คน"
            )
        
        user_count = get_user_count()
        
        stats = (
            f"📊 *สถิติ Broadcast*\n\n"
            f"👥 ผู้ใช้ทั้งหมด: {user_count} คน\n"
            f"📢 ส่งแล้ว: {total_broadcasts} ครั้ง\n"
            f"✅ ข้อความทั้งหมด: {total_sent} ข้อความ\n\n"
            f"📝 *ประวัติล่าสุด:*\n" +
            "\n".join(recent_broadcasts[:5]) if recent_broadcasts else "ยังไม่มีประวัติ"
        )
        
        return stats
    except Exception as e:
        logger.error(f"Error getting broadcast stats: {e}")
        return f"❌ เกิดข้อผิดพลาด: {str(e)}"

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
