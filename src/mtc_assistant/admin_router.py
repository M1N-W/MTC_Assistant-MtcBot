# -*- coding: utf-8 -*-
"""
MTC Assistant - Admin command routing
"""

import threading
import time
from typing import Optional

from linebot.v3.messaging import TextMessage

import mtc_assistant.broadcast as broadcast
from mtc_assistant.config import logger


def handle_admin_command(user_id: str, user_message: str) -> Optional[TextMessage]:
    reply_message = None

    if user_message.startswith("ประกาศ "):
        msg = user_message.replace("ประกาศ ", "", 1).strip()
        if msg:
            announcement = broadcast.create_announcement("ประกาศจากผู้ดูแล", msg)

            def _do_broadcast(ann=announcement, aid=user_id):
                result = broadcast.broadcast_message(ann)
                broadcast.save_broadcast_history(aid, ann, result)
                logger.info(f"Broadcast complete: {result['message']}")

            threading.Thread(target=_do_broadcast, daemon=True).start()
            reply_message = TextMessage(
                text=f"กำลังส่งประกาศในพื้นหลัง...\n"
                     f"เวลา {time.strftime('%H:%M:%S')}"
            )

    elif user_message in ["สถิติประกาศ", "broadcast stats"]:
        reply_message = TextMessage(text=broadcast.get_broadcast_stats())

    elif user_message in ["จำนวนผู้ใช้", "user count"]:
        count = broadcast.get_user_count()
        reply_message = TextMessage(
            text=f"จำนวนผู้ใช้ทั้งหมด: {count} คน"
        )

    try:
        from mtc_assistant.admin_impersonate import (
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

    try:
        from mtc_assistant.user_blacklist import (
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

    if user_message in ["admin", "คำสั่งแอดมิน"]:
        admin_help = (
            "คำสั่งแอดมิน\n\n"
            "Broadcast\n"
            "  ประกาศ [ข้อความ]\n"
            "  สถิติประกาศ\n"
            "  จำนวนผู้ใช้\n\n"
            "Impersonate\n"
            "  ดูผู้ใช้\n"
            "  ส่งถึง [user_id] [ข้อความ]\n"
            "  ทดสอบส่ง [ข้อความ]\n\n"
            "Blacklist\n"
            "  แบน [user_id] [เหตุผล]\n"
            "  ปลดแบน [user_id]\n"
            "  รายชื่อแบน\n"
            "  สถิติแบน"
        )
        reply_message = TextMessage(text=admin_help)

    return reply_message
