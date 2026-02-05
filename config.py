# -*- coding: utf-8 -*-
"""
MTC Assistant - Configuration Module
Contains all constants, settings, messages, and data structures
"""

import os
import datetime
import logging
from zoneinfo import ZoneInfo

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
LOG_LEVEL = logging.DEBUG if os.environ.get("DEBUG", "false").lower() in ("1", "true", "yes") else logging.INFO
logger = logging.getLogger("mtc_assistant")

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s %(levelname)s %(message)s"
    )
    logger.setLevel(LOG_LEVEL)
    return logger

# ============================================================================
# ENVIRONMENT VARIABLES & CREDENTIALS
# ============================================================================
ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
FIREBASE_KEY_PATH = "firebase_key.json"

# Safe PORT parsing
try:
    PORT = int(os.environ.get('PORT', 5001))
except (ValueError, TypeError):
    logger.warning("Invalid PORT value, using default 5001")
    PORT = 5001

FLASK_DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

# Gemini Model Configuration (read from Render ENV)
GEMINI_API_KEY_V3 = os.environ.get("GEMINI_API_KEY_PRIMARY")
GEMINI_API_KEY_V25 = os.environ.get("GEMINI_API_KEY_SECONDARY")

GEMINI_MODEL_V3 = os.environ.get("GEMINI_MODEL_PRIMARY", "gemini-3-flash-preview")
GEMINI_MODEL_V25 = os.environ.get("GEMINI_MODEL_SECONDARY", "gemini-2.5-flash-preview")

# ============================================================================
# RATE LIMITING CONFIGURATION
# ============================================================================
RATE_LIMIT_MAX = int(os.environ.get("RATE_LIMIT_MAX", 6))
RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", 60))

# ============================================================================
# ADMIN CONFIGURATION
# ============================================================================
# ใส่ LINE User ID ของคุณที่นี่ (หาได้จาก log เมื่อส่งข้อความ)
# หรือตั้งค่าใน environment variable
ADMIN_USER_IDS = os.environ.get('ADMIN_USER_IDS', '').split(',')
if not ADMIN_USER_IDS or ADMIN_USER_IDS == ['']:
    # Default admin (ใส่ user_id ของคุณที่นี่)
    ADMIN_USER_IDS = []  # เพิ่ม user_id ของคุณตรงนี้เช่น ['U1234567890abcdef']
    logger.warning("No admin users configured. Set ADMIN_USER_IDS in environment or config.")

# ============================================================================
# CONSTANTS
# ============================================================================
LINE_MAX_TEXT = 5000
LINE_SAFE_TRUNCATE = 4000  # To avoid cutting in the middle of multi-byte chars
LOCAL_TZ = ZoneInfo("Asia/Bangkok")

# ============================================================================
# LINKS & RESOURCES
# ============================================================================
WORKSHEET_LINK = "https://docs.google.com/spreadsheets/d/1SwKs4s8HJt2HxAzj_StIh_nopVMe1kwqg7yW13jOdQ4/edit?usp=sharing"
SCHOOL_LINK = "https://www.ben.ac.th/main/"
TIMETABLE_IMG = "https://img2.pic.in.th/-212cf066040445937.jpg"
GRADE_LINK = "http://www.dograde2.online/bjrb/"
ABSENCE_LINK = "https://forms.gle/WjCBTYNxEeCpHShr9"
Bio_LINK = "https://drive.google.com/file/d/1zd5NND3612JOym6HSzKZnqAS42TH9gmh/view?usp=sharing"
Physic_LINK = "https://drive.google.com/file/d/15oSPs3jFYpvJRUkFqrCSpETGwOoK0Qpv/view?usp=sharing"

# ============================================================================
# MESSAGES
# ============================================================================
MESSAGES = {
    "IDENTITY": (
        "ผมเป็นบอทผู้ช่วยอเนกประสงค์ของห้อง MTC ม.4/2 "
        "ผมช่วยได้หลายอย่าง เช่น แจ้งตาราง, ลิงก์เว็บโรงเรียน, หาตารางสอน, "
        "เช็คเกรด, ดูเวลาคาบถัดไป, และตอบคำถามต่าง ๆ ด้วยเอไอ"
    ),
    "AI_DISABLED": "ขออภัยครับ ระบบ AI ยังไม่เปิดใช้งานในขณะนี้",
    "AI_NO_RESPONSE": "ขออภัยครับ ระบบ AI ตอบไม่ได้ในขณะนี้ ลองใหม่อีกครั้ง",
    "AI_ERROR": "ขออภัยครับ ตอนนี้ผมมีปัญหาในการเชื่อมต่อกับ AI ลองใหม่อีกครั้งนะ",
    "RATE_LIMITED": "คุณส่งข้อความเร็วจนเกินไป ลองช้าลงอีกนิดนะครับ",
    "INVALID_MESSAGE": "ขออภัยครับ ผมรับข้อความประเภทนี้ไม่ได้นะ ลองพิมพ์ข้อความ",
    "NO_CLASS_TODAY": "วันนี้วันหยุดไม่ใช่วันเรียน กลับไปนอนไป๊ 🎉",
    "NO_CLASS_LEFT": "วันนี้ไม่มีคาบเรียนแล้วครับ กลับบ้านได้เลยครับ 🏠",
    "ACTION_ERROR": "ขออภัยครับ เกิดข้อผิดพลาดขณะประมวลผลคำสั่งของคุณ",
}

# ============================================================================
# EXAM DATES (Multi-date support)
# ============================================================================
EXAM_DATES = {
    "กลางภาค": [
        datetime.date(2025, 12, 21),
        datetime.date(2025, 12, 23),
        datetime.date(2025, 12, 25),
    ],
    "ปลายภาค": [
        datetime.date(2026, 2, 16),
        datetime.date(2026, 2, 18),
        datetime.date(2026, 2, 20),
    ]
}

# ============================================================================
# CLASS SCHEDULE
# ============================================================================
SCHEDULE = {
    0: [  # วันจันทร์
        {"start": "08:30", "end": "09:25", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "331"},
        {"start": "09:25", "end": "10:20", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "331"},
        {"start": "10:20", "end": "11:15", "subject": "เคมี (ครูพิทยาภรณ์)", "room": "311"},
        {"start": "11:15", "end": "12:10", "subject": "แนะแนว (ครูทศพร)", "room": "947"},
        {"start": "13:05", "end": "14:00", "subject": "นาฏศิลป์ (ครูบังเอิญ)", "room": "575"},
        {"start": "14:00", "end": "14:55", "subject": "การงานอาชีพ (ครูอัญชลี)", "room": "947"},
        {"start": "14:55", "end": "15:50", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
        {"start": "15:50", "end": "16:45", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
    ],
    1: [  # วันอังคาร
        {"start": "08:30", "end": "09:25", "subject": "เคมี (ครูพิทยาภรณ์)", "room": "311"},
        {"start": "09:25", "end": "10:20", "subject": "เคมี (ครูพิทยาภรณ์)", "room": "311"},
        {"start": "10:20", "end": "11:15", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "333"},
        {"start": "11:15", "end": "12:10", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "333"},
        {"start": "13:05", "end": "14:00", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
        {"start": "14:00", "end": "14:55", "subject": "สังคมศึกษา (ครูบังอร)", "room": "947"},
        {"start": "14:55", "end": "15:50", "subject": "ไทย (ครูเบญจมาศ)", "room": "947"},
        {"start": "15:50", "end": "16:45", "subject": "อังกฤษพื้นฐาน (ครูวาสนา)", "room": "947"},
    ],
    2: [  # วันพุธ
        {"start": "08:30", "end": "09:25", "subject": "อังกฤษพื้นฐาน (ครูวาสนา)", "room": "947"},
        {"start": "09:25", "end": "10:20", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
        {"start": "10:20", "end": "11:15", "subject": "ประวัติศาสตร์ (ครูณฐพร)", "room": "947"},
        {"start": "11:15", "end": "12:10", "subject": "คณิตพื้นฐาน (ครูปรียา)", "room": "947"},
    ],
    3: [  # วันพฤหัสบดี
        {"start": "08:30", "end": "09:25", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
        {"start": "09:25", "end": "10:20", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
        {"start": "10:20", "end": "11:15", "subject": "ชีววิทยา (ครูพิชามญช์)", "room": "323"},
        {"start": "11:15", "end": "12:10", "subject": "ไทย (ครูเบญจมาศ)", "room": "947"},
        {"start": "13:05", "end": "14:00", "subject": "สุขศึกษา&พละศึกษา (ครูนรเศรษฐ์)", "room": "ห้องเรียน/โดม"},
        {"start": "14:00", "end": "14:55", "subject": "อังกฤษเพิ่มเติม (Teacher Mitch)", "room": "947"},
        {"start": "14:55", "end": "15:50", "subject": "คณิตพื้นฐาน (ครูปรียา)", "room": "947"},
    ],
    4: [  # วันศุกร์
        {"start": "08:30", "end": "09:25", "subject": "ชีววิทยา (ครูพิชามญช์)", "room": "323"},
        {"start": "09:25", "end": "10:20", "subject": "ชีววิทยา (ครูพิชามญช์)", "room": "323"},
        {"start": "10:20", "end": "11:15", "subject": "อังกฤษพื้นฐาน (ครูวาสนา)", "room": "947"},
        {"start": "11:15", "end": "12:10", "subject": "สังคมศึกษา (ครูบังอร)", "room": "947"},
        {"start": "13:05", "end": "14:00", "subject": "คอมพิวเตอร์ (ครูจินดาพร)", "room": "221"},
        {"start": "14:00", "end": "14:55", "subject": "คอมพิวเตอร์ (ครูจินดาพร)", "room": "221"},
        {"start": "14:55", "end": "15:50", "subject": "IS (ครูปรียา)", "room": "947"},
        {"start": "15:50", "end": "16:45", "subject": "IS (ครูปรียา)", "room": "947"},
    ]
}

# ============================================================================
# CONFIGURATION VALIDATION
# ============================================================================
def validate_config():
    if not ACCESS_TOKEN:
        logger.warning("CHANNEL_ACCESS_TOKEN not set; LINE API calls will fail.")
    if not CHANNEL_SECRET:
        logger.warning("CHANNEL_SECRET not set; signature verification may fail.")
    if not (GEMINI_API_KEY_V3 or GEMINI_API_KEY_V25):
        logger.info("No Gemini API keys set; AI features disabled.")
    logger.info(f"Configuration loaded: PORT={PORT}, DEBUG={FLASK_DEBUG}")
