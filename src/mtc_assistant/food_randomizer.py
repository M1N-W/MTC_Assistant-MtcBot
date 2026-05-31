# -*- coding: utf-8 -*-
"""
MTC Assistant - Food randomizer
"""

import random

from linebot.v3.messaging import TextMessage


FOOD_OPTIONS = [
    "ข้าวกะเพราไก่ไข่ดาว",
    "ข้าวหมูทอดกระเทียม",
    "ข้าวมันไก่",
    "ก๋วยเตี๋ยวต้มยำ",
    "ข้าวผัด",
    "สุกี้น้ำ",
    "ผัดซีอิ๊ว",
    "ข้าวไข่เจียวหมูสับ",
    "ราดหน้า",
    "ข้าวแกงกะหรี่",
]


def handle_food_randomizer_command(user_message: str) -> TextMessage:
    """Return one simple meal suggestion for food-randomizer commands."""
    choice = random.choice(FOOD_OPTIONS)
    return TextMessage(text=f"วันนี้ลองกิน {choice} ดีไหมครับ")
