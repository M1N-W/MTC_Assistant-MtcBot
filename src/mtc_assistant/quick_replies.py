# -*- coding: utf-8 -*-
"""
MTC Assistant - Quick Reply builders
"""

from linebot.v3.messaging import QuickReply, QuickReplyItem, MessageAction

from mtc_assistant.constants import SUBJECTS


def build_subject_quick_reply() -> QuickReply:
    quick_reply_items = []
    for i in range(0, min(len(SUBJECTS), 13)):
        quick_reply_items.append(
            QuickReplyItem(
                action=MessageAction(label=SUBJECTS[i], text=SUBJECTS[i])
            )
        )

    return QuickReply(items=quick_reply_items)


def build_due_date_quick_reply() -> QuickReply:
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="วันนี้", text="วันนี้")),
        QuickReplyItem(action=MessageAction(label="พรุ่งนี้", text="พรุ่งนี้")),
        QuickReplyItem(action=MessageAction(label="วันจันทร์", text="วันจันทร์")),
        QuickReplyItem(action=MessageAction(label="วันอังคาร", text="วันอังคาร")),
        QuickReplyItem(action=MessageAction(label="วันพุธ", text="วันพุธ")),
        QuickReplyItem(action=MessageAction(label="วันพฤหัส", text="วันพฤหัสบดี")),
        QuickReplyItem(action=MessageAction(label="วันศุกร์", text="วันศุกร์")),
        QuickReplyItem(action=MessageAction(label="สัปดาห์หน้า", text="สัปดาห์หน้า")),
        QuickReplyItem(action=MessageAction(label="ยกเลิก", text="ยกเลิกการบ้าน")),
    ])


def build_unknown_message_quick_reply() -> QuickReply:
    return QuickReply(items=[
        QuickReplyItem(action=MessageAction(label="ถาม AI", text="ai")),
        QuickReplyItem(action=MessageAction(label="ดูคำสั่ง", text="ช่วยเหลือ")),
        QuickReplyItem(action=MessageAction(label="การบ้าน", text="การบ้าน")),
        QuickReplyItem(action=MessageAction(label="ตารางเรียน", text="ตารางเรียน")),
    ])
