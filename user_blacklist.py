# -*- coding: utf-8 -*-
"""
MTC Assistant - User Blacklist System
ระบบแบนผู้ใช้และจัดการ spam
"""

import time
import json
from typing import Dict, Set, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from config import logger, LOCAL_TZ

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
    Manage permanent and temporary bans
    
    Usage:
        blacklist = BlacklistManager()
        
        # Check if user is banned
        if blacklist.is_banned(user_id):
            return "You are banned!"
        
        # Ban a user
        blacklist.ban_user(user_id, admin_id, "Spamming")
        
        # Unban a user
        blacklist.unban_user(user_id)
    """
    
    def __init__(self, storage_file: str = "blacklist.json"):
        """Initialize blacklist manager"""
        self.storage_file = storage_file
        self.blacklist: Dict[str, BanRecord] = {}
        self.load_blacklist()
    
    def load_blacklist(self):
        """Load blacklist from file"""
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.blacklist = {
                    user_id: BanRecord(**record) 
                    for user_id, record in data.items()
                }
            logger.info(f"Loaded {len(self.blacklist)} banned users")
        except FileNotFoundError:
            logger.info("No blacklist file found, starting fresh")
            self.blacklist = {}
        except Exception as e:
            logger.error(f"Error loading blacklist: {e}")
            self.blacklist = {}
    
    def save_blacklist(self):
        """Save blacklist to file"""
        try:
            data = {
                user_id: asdict(record) 
                for user_id, record in self.blacklist.items()
            }
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(self.blacklist)} banned users")
        except Exception as e:
            logger.error(f"Error saving blacklist: {e}")
    
    def is_banned(self, user_id: str) -> bool:
        """Check if user is banned"""
        return user_id in self.blacklist
    
    def ban_user(
        self, 
        user_id: str, 
        admin_id: str, 
        reason: str = "Violation of terms",
        permanent: bool = True
    ) -> bool:
        """
        Ban a user permanently
        
        Args:
            user_id: User ID to ban
            admin_id: Admin who issued the ban
            reason: Reason for ban
            permanent: Whether ban is permanent
        
        Returns:
            True if successful
        """
        try:
            now = datetime.now(tz=LOCAL_TZ).isoformat()
            
            self.blacklist[user_id] = BanRecord(
                user_id=user_id,
                banned_at=now,
                banned_by=admin_id,
                reason=reason,
                is_permanent=permanent
            )
            
            self.save_blacklist()
            logger.warning(f"User {user_id} banned by {admin_id}: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Error banning user: {e}")
            return False
    
    def unban_user(self, user_id: str) -> bool:
        """
        Unban a user
        
        Args:
            user_id: User ID to unban
        
        Returns:
            True if successful
        """
        try:
            if user_id in self.blacklist:
                del self.blacklist[user_id]
                self.save_blacklist()
                logger.info(f"User {user_id} unbanned")
                return True
            else:
                logger.warning(f"User {user_id} not in blacklist")
                return False
        except Exception as e:
            logger.error(f"Error unbanning user: {e}")
            return False
    
    def get_ban_info(self, user_id: str) -> Optional[BanRecord]:
        """Get ban information for a user"""
        return self.blacklist.get(user_id)
    
    def get_all_banned(self) -> Dict[str, BanRecord]:
        """Get all banned users"""
        return self.blacklist.copy()
    
    def get_stats(self) -> str:
        """Get blacklist statistics"""
        total = len(self.blacklist)
        permanent = sum(1 for r in self.blacklist.values() if r.is_permanent)
        
        message = f"🚫 *Blacklist Statistics*\n\n"
        message += f"Total banned: {total}\n"
        message += f"Permanent: {permanent}\n"
        message += f"Temporary: {total - permanent}\n"
        
        return message
    
    def format_ban_message(self, user_id: str) -> str:
        """Format ban message for user"""
        record = self.get_ban_info(user_id)
        
        if not record:
            return "⚠️ คุณถูกจำกัดการใช้งานชั่วคราว"
        
        message = "🚫 *คุณถูกแบนจากการใช้งาน*\n\n"
        message += f"เหตุผล {record.reason}\n"
        message += f"วันที่แบน {record.banned_at}\n"
        
        if record.is_permanent:
            message += f"\nสถานะ = ถาวร\n"
            message += f"หากต้องการอุทธรณ์ กรุณาติดต่อผู้ดูแลระบบ"
        else:
            message += f"\nสถานะ = ชั่วคราว"
        
        return message

# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

_blacklist_manager: Optional[BlacklistManager] = None

def get_blacklist_manager() -> BlacklistManager:
    """Get or create global blacklist manager"""
    global _blacklist_manager
    if _blacklist_manager is None:
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
            "⚠️ รูปแบบคำสั่ง\n"
            "แบน [user_id] [เหตุผล]\n\n"
            "ตัวอย่าง:\n"
            "แบน U1234567890 Spamming"
        )
    
    target_user_id = parts[1]
    reason = parts[2] if len(parts) > 2 else "ไม่ระบุเหตุผล"
    
    # ป้องกันไม่ให้แบน admin
    from config import ADMIN_USER_IDS
    if target_user_id in ADMIN_USER_IDS:
        return "❌ ไม่สามารถแบน Admin ได้"
    
    success = blacklist.ban_user(target_user_id, admin_id, reason)
    
    if success:
        return f"✅ แบน {target_user_id} สำเร็จ\nเหตุผล: {reason}"
    else:
        return "❌ เกิดข้อผิดพลาดในการแบน"

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
            "⚠️ รูปแบบคำสั่ง\n"
            "ปลดแบน [user_id]\n\n"
            "ตัวอย่าง:\n"
            "ปลดแบน U1234567890"
        )
    
    target_user_id = parts[1]
    success = blacklist.unban_user(target_user_id)
    
    if success:
        return f"✅ ปลดแบน {target_user_id} สำเร็จ"
    else:
        return f"⚠️ {target_user_id} ไม่อยู่ในรายการแบน"

def handle_list_banned_command(admin_id: str, user_message: str = "") -> str:
    """
    Handle list banned users command
    
    Command: รายชื่อแบน
    """
    blacklist = get_blacklist_manager()
    banned = blacklist.get_all_banned()
    
    if not banned:
        return "📋 ไม่มีผู้ใช้ที่ถูกแบนในระบบ"
    
    message = f"🚫 *รายชื่อผู้ใช้ที่ถูกแบน* ({len(banned)} คน)\n\n"
    
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

def check_user_banned(user_id: str) -> tuple[bool, str]:
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
        from user_blacklist import get_admin_ban_commands, check_user_banned
        
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
