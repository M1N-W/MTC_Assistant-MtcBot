# -*- coding: utf-8 -*-
"""
MTC Assistant - Rate limiting
"""

import time
import threading
from typing import Dict, List

from mtc_assistant.config import logger, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW


_user_message_history: Dict[str, List[float]] = {}
_rate_limit_lock = threading.Lock()
_banned_users: Dict[str, float] = {}


def cleanup_rate_limit_data():
    """Clean up old rate limit data to prevent memory leaks"""
    now_ts = time.time()
    with _rate_limit_lock:
        old_users = []
        for user_id, timestamps in _user_message_history.items():
            recent = [t for t in timestamps if now_ts - t < 3600]
            if recent:
                _user_message_history[user_id] = recent
            else:
                old_users.append(user_id)

        for user_id in old_users:
            del _user_message_history[user_id]

        expired_bans = []
        for user_id, ban_until in _banned_users.items():
            if now_ts >= ban_until:
                expired_bans.append(user_id)

        for user_id in expired_bans:
            del _banned_users[user_id]


def auto_cleanup():
    while True:
        time.sleep(600)
        cleanup_rate_limit_data()


cleanup_thread = threading.Thread(target=auto_cleanup, daemon=True)
cleanup_thread.start()


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

        if not recent:
            _user_message_history.pop(user_id, None)
            return False

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


def get_rate_limit_stats() -> dict:
    with _rate_limit_lock:
        total_users = len(_user_message_history)
        total_messages = sum(len(msgs) for msgs in _user_message_history.values())
        banned_users = len(_banned_users)

    return {
        "total_users": total_users,
        "total_messages": total_messages,
        "tracked_users": total_users,
        "banned_users": banned_users,
    }
