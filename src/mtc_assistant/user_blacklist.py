# -*- coding: utf-8 -*-
"""
MTC Assistant - User Blacklist System (FIXED)
ระบบแบนผู้ใช้และจัดการ spam
✅ FIXED: Type hint compatibility for Python 3.7+
"""

import time
import json  # kept only for potential future export helpers
from threading import Lock
from typing import Dict, Set, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from mtc_assistant.config import logger, LOCAL_TZ

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class BanRecord:
    """Record of a banned user"""
    user_id: str
    banned_at: str
    banned_by: str  # admin user_id
    reason: str
    is_permanent: bool = True

# ============================================================================
# BLACKLIST MANAGER
# ============================================================================

class BlacklistManager:
    """
    Manage permanent bans backed by Firebase Firestore.

    An in-memory cache (_cache) is kept in sync so every is_banned() check
    is O(1) without a network round-trip.  Writes go to both Firestore and
    the cache atomically (within Python's GIL).

    Usage:
        blacklist = BlacklistManager(db=firestore_client)

        if blacklist.is_banned(user_id):
            return "You are banned!"

        blacklist.ban_user(user_id, admin_id, "Spamming")
        blacklist.unban_user(user_id)
    """

    def __init__(self, db=None):
        """
        Args:
            db: Firebase Firestore client.  When None the manager operates in
                memory-only mode (bans survive the request but not a restart).
        """
        self.db = db
        self._cache: Dict[str, BanRecord] = {}
        if self.db:
            self.load_blacklist()
        else:
            # Expected during startup: the singleton is created before
            # Firebase finishes its async connect; main.py wires `db` in
            # later via `_bm.db = db; _bm.load_blacklist()`.  Use DEBUG so
            # we don't pollute production logs with a misleading warning.
            logger.debug(
                "BlacklistManager initialised without Firestore client "
                "(will be wired up after Firebase connects)."
            )

    def load_blacklist(self):
        """Load all ban records from Firestore into the in-memory cache."""
        try:
            docs = self.db.collection('blacklist').stream()
            self._cache = {
                doc.id: BanRecord(**doc.to_dict()) for doc in docs
            }
            logger.info(f"Loaded {len(self._cache)} banned users from Firestore")
        except Exception as e:
            logger.error(f"Error loading blacklist from Firestore: {e}")
            self._cache = {}

    def is_banned(self, user_id: str) -> bool:
        """O(1) ban check — reads only from the in-memory cache."""
        return user_id in self._cache

    def ban_user(
        self,
        user_id: str,
        admin_id: str,
        reason: str = "Violation of terms",
        permanent: bool = True
    ) -> bool:
        """
        Ban a user.  Writes to Firestore first; updates cache on success.

        Returns:
            True if the ban was stored successfully.
        """
        try:
            now = datetime.now(tz=LOCAL_TZ).isoformat()
            record = BanRecord(
                user_id=user_id,
                banned_at=now,
                banned_by=admin_id,
                reason=reason,
                is_permanent=permanent,
            )
            if self.db:
                self.db.collection('blacklist').document(user_id).set(asdict(record))
            # Update cache only after a successful write
            self._cache[user_id] = record
            logger.warning(f"User {user_id} banned by {admin_id}: {reason}")
            return True
        except Exception as e:
            logger.error(f"Error banning user {user_id}: {e}")
            return False

    def unban_user(self, user_id: str) -> bool:
        """
        Remove a ban.  Deletes from Firestore first; updates cache on success.

        Returns:
            True if the user was found and unbanned.
        """
        if user_id not in self._cache:
            logger.warning(f"Unban requested for {user_id} but they are not banned")
            return False
        try:
            if self.db:
                self.db.collection('blacklist').document(user_id).delete()
            del self._cache[user_id]
            logger.info(f"User {user_id} unbanned")
            return True
        except Exception as e:
            logger.error(f"Error unbanning user {user_id}: {e}")
            return False

    def get_ban_info(self, user_id: str) -> Optional[BanRecord]:
        """Get ban information for a user."""
        return self._cache.get(user_id)

    def get_all_banned(self) -> Dict[str, BanRecord]:
        """Return a snapshot of all banned users."""
        return self._cache.copy()

    def get_stats(self) -> str:
        """Get blacklist statistics."""
        total = len(self._cache)
        permanent = sum(1 for r in self._cache.values() if r.is_permanent)
        message = "📊 *รายงานสถิติบัญชีดำ (Blacklist)* 🚫\n\n"
        message += f"Total banned: {total}\n"
        message += f"Permanent: {permanent}\n"
        message += f"Temporary: {total - permanent}\n"
        return message

    def format_ban_message(self, user_id: str) -> str:
        """Format a user-facing ban message."""
        record = self.get_ban_info(user_id)
        if not record:
            return "อุ๊ย! ดูเหมือนคุณจะถูกระงับการใช้งานชั่วคราวนะฮะ 🥺"
        message = "แงงง.. คุณถูกจำกัดสิทธิ์การใช้งานบอทฮะ 🚫\n\n"
        message += f"📝 สาเหตุ: {record.reason}\n"
        message += f"📅 ตั้งแต่วันที่: {record.banned_at}\n"
        if record.is_permanent:
            message += "\nสถานะ: ถาวร 🔒\n"
            message += "(ถ้าคิดว่านี่คือเรื่องเข้าใจผิด ทักหาแอดมินให้ช่วยตรวจสอบได้เลยน้า ✌️)"
        else:
            message += "\nสถานะ: ชั่วคราว ⏳"
        return message

# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

_blacklist_manager: Optional[BlacklistManager] = None
_blacklist_lock = Lock()


def get_blacklist_manager() -> BlacklistManager:
    """
    Return the process-wide BlacklistManager singleton.

    Uses double-checked locking so that even under concurrent Flask threads
    only one instance is ever created.  Wire up Firestore via
    ``get_blacklist_manager().db = db`` (and call ``.load_blacklist()``)
    during app startup in main.py.
    """
    global _blacklist_manager
    if _blacklist_manager is None:
        with _blacklist_lock:
            if _blacklist_manager is None:   # second check inside the lock
                _blacklist_manager = BlacklistManager()
    return _blacklist_manager

# ============================================================================
# ADMIN COMMANDS
# ============================================================================

def handle_ban_user_command(admin_id: str, user_message: str) -> str:
    """
    Handle ban user command
    
    Format: แบน [user_id] [reason]
    Example: แบน U1234567890 Spamming
    """
    blacklist = get_blacklist_manager()
    
    parts = user_message.split(maxsplit=2)
    
    if len(parts) < 2:
        return (
            "บอสครับ! รูปแบบคำสั่งไม่ถูกฮะ 🕵️‍♂️ ต้องพิมพ์แบบนี้:\n"
            "แบน [รหัสผู้ใช้] [เหตุผล]"
        )
    
    target_user_id = parts[1]
    reason = parts[2] if len(parts) > 2 else "ไม่ระบุเหตุผล"
    
    # ป้องกันไม่ให้แบน admin
    from mtc_assistant.config import ADMIN_USER_IDS
    if target_user_id in ADMIN_USER_IDS:
        return "บอสจะแบนพวกเดียวกันไม่ได้นะฮะ! 🛑"
    
    success = blacklist.ban_user(target_user_id, admin_id, reason)
    
    if success:
        return f"🎯 จัดการแบนเป้าหมาย {target_user_id} เรียบร้อยครับบอส!\nข้อหา: {reason} 🤫"
    else:
        return "❌ ภารกิจล้มเหลวฮะ ระบบแบนมีปัญหา"

def handle_unban_user_command(admin_id: str, user_message: str) -> str:
    """
    Handle unban user command
    
    Format: ปลดแบน [user_id]
    Example: ปลดแบน U1234567890
    """
    blacklist = get_blacklist_manager()
    
    parts = user_message.split()
    
    if len(parts) < 2:
        return (
            "บอสครับ! จะให้ผมปลดแบนใคร พิมพ์มาแบบนี้นะฮะ:\n"
            "ปลดแบน [รหัสผู้ใช้]"
        )
    
    target_user_id = parts[1]
    success = blacklist.unban_user(target_user_id)
    
    if success:
        return f"🔓 ปลดล็อกเป้าหมาย {target_user_id} ให้กลับมาใช้งานได้แล้วครับบอส!"
    else:
        return f"🧐 เป้าหมาย {target_user_id} ไม่ได้อยู่ในแฟ้มบัญชีดำนะฮะ"

def handle_list_banned_command(admin_id: str, user_message: str = "") -> str:
    """
    Handle list banned users command
    
    Command: รายชื่อแบน
    """
    blacklist = get_blacklist_manager()
    banned = blacklist.get_all_banned()
    
    if not banned:
        return "📋 แฟ้มบัญชีดำว่างเปล่าครับบอส! ตอนนี้ทุกคนเป็นเด็กดีหมดเลย 😇"
    
    message = f"📂 *แฟ้มลับ: รายชื่อบัญชีดำ* ({len(banned)} เป้าหมาย)\n\n"
    
    for i, (user_id, record) in enumerate(banned.items(), 1):
        message += f"{i}. `{user_id}`\n"
        message += f"   เหตุผล: {record.reason}\n"
        message += f"   วันที่: {record.banned_at[:10]}\n\n"
    
    return message

def handle_ban_stats_command(admin_id: str, user_message: str = "") -> str:
    """Handle ban statistics command"""
    blacklist = get_blacklist_manager()
    return blacklist.get_stats()

# ============================================================================
# INTEGRATION HELPER
# ============================================================================

def check_user_banned(user_id: str) -> Tuple[bool, str]:  # ✅ FIXED: Use Tuple from typing
    """
    Check if user is banned and return appropriate message
    
    Returns:
        (is_banned, message)
    """
    blacklist = get_blacklist_manager()
    
    if blacklist.is_banned(user_id):
        message = blacklist.format_ban_message(user_id)
        return True, message
    
    return False, ""

def get_admin_ban_commands():
    """
    Return admin ban commands for integration
    
    Usage in handlers.py:
        from mtc_assistant.user_blacklist import get_admin_ban_commands, check_user_banned
        
        # In handle_message:
        # Check if banned
        is_banned, ban_msg = check_user_banned(user_id)
        if is_banned:
            reply_to_line(event.reply_token, [TextMessage(text=ban_msg)])
            return
        
        # Admin commands
        if user_id in ADMIN_USER_IDS:
            for keywords, handler in get_admin_ban_commands():
                # ... match and execute
    """
    return [
        (("แบน", "ban user"), handle_ban_user_command),
        (("ปลดแบน", "unban user"), handle_unban_user_command),
        (("รายชื่อแบน", "banned list", "ดูคนแบน"), handle_list_banned_command),
        (("สถิติแบน", "ban stats"), handle_ban_stats_command),
    ]

def get_admin_ban_help() -> str:
    """Return help text for ban commands"""
    return """
🚫 *คำสั่งจัดการ Blacklist*

• แบน [user_id] [เหตุผล]
  ตัวอย่าง: แบน U1234567890 Spamming

• ปลดแบน [user_id]
  ตัวอย่าง: ปลดแบน U1234567890

• รายชื่อแบน
  → ดูรายชื่อผู้ถูกแบนทั้งหมด

• สถิติแบน
  → ดูสถิติการแบน
"""

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'BlacklistManager',
    'get_blacklist_manager',
    'check_user_banned',
    'get_admin_ban_commands',
    'get_admin_ban_help',
]