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

GEMINI_MODEL_V3 = os.environ.get("GEMINI_MODEL_PRIMARY", "gemini-2.0-flash")
GEMINI_MODEL_V25 = os.environ.get("GEMINI_MODEL_SECONDARY", "gemini-2.5-flash-preview-04-17")

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
ADMIN_USER_IDS = [
    uid.strip()
    for uid in os.environ.get('ADMIN_USER_IDS', '').split(',')
    if uid.strip()
]
if not ADMIN_USER_IDS:
    # Default admin (ใส่ user_id ของคุณที่นี่)
    ADMIN_USER_IDS = []  # เพิ่ม user_id ของคุณตรงนี้เช่น ['U1234567890abcdef']
    logger.warning("No admin users configured. Set ADMIN_USER_IDS in environment or config.")

# ============================================================================
# CONSTANTS
# ============================================================================
LINE_MAX_TEXT = 5000
LINE_SAFE_TRUNCATE = 4800  # To avoid cutting in the middle of multi-byte chars
LOCAL_TZ = ZoneInfo("Asia/Bangkok")

# ============================================================================
# LINKS & RESOURCES
# ============================================================================
WORKSHEET_LINK = "https://docs.google.com/spreadsheets/d/1SwKs4s8HJt2HxAzj_StIh_nopVMe1kwqg7yW13jOdQ4/edit?usp=sharing"
SCHOOL_LINK = "https://www.ben.ac.th/main/"
TIMETABLE_IMG = "https://img2.pic.in.th/186308.jpg"
GRADE_LINK = "http://www.dograde2.online/bjrb/"
ABSENCE_LINK = "https://forms.gle/WjCBTYNxEeCpHShr9"
Bio_LINK = "https://drive.google.com/file/d/1zd5NND3612JOym6HSzKZnqAS42TH9gmh/view?usp=sharing"
Physic_LINK = "https://drive.google.com/file/d/15oSPs3jFYpvJRUkFqrCSpETGwOoK0Qpv/view?usp=sharing"

# ============================================================================
# MESSAGES
# ============================================================================
MESSAGES = {
    "IDENTITY": (
        "สวัสดีคร้าบ! เราคือบอทผู้ช่วยประจำห้อง MTC ม.5/2 เอง 🤖✨\n"
        "มีอะไรให้ช่วยบอกได้เลยนะ ไม่ว่าจะดูตารางเรียน 📚 ขอลิงก์เว็บโรงเรียน 🌐 "
        "เช็คเกรด 💯 ดูเวลาคาบถัดไป ⏰ หรือถ้ามีคำถามอะไรยากๆ ก็ให้ AI ของเราช่วยหาคำตอบได้เลย!"
    ),
    "AI_DISABLED": "แงงง ระบบ AI ยังไม่ตื่นเลยฮะ 😴 รอแอดมินมาเปิดสวิตช์แป๊บนึงน้า",
    "AI_NO_RESPONSE": "มึนตึ้บเลยฮะ 😵‍💫 AI คิดคำตอบไม่ออก ลองพิมพ์ถามมาใหม่อีกรอบได้มั้ยเอ่ย?",
    "AI_ERROR": "อูยยย สายส่งข้อมูล AI สะดุดฮะ 🔌 รบกวนพิมพ์ถามมาใหม่อีกทีน้า",
    "RATE_LIMITED": "โอ๊ะโอ! พิมพ์เร็วจนระบบเราอ่านไม่ทันแล้วว 💨 พักหายใจสักแป๊บแล้วค่อยทักมาใหม่น้า 🥺",
    "INVALID_MESSAGE": "เรายังอ่านสติกเกอร์หรือรูปภาพไม่ค่อยเก่งฮะ 😅 พิมพ์เป็นข้อความมาคุยกันดีกว่าน้า",
    "NO_CLASS_TODAY": "เย้! วันนี้ไม่มีเรียนฮะ 🎉 พักผ่อนให้เต็มที่ ชาร์จแบตให้ตัวเองกันเลยยย!",
    "NO_CLASS_LEFT": "หมดคาบเรียนของวันนี้แล้ว! 🎒 เก็บกระเป๋าแล้วเดินทางกลับบ้านกันดีๆ นะทุกคน",
    "ACTION_ERROR": "อุ๊ย! ระบบสะดุดกึกกักนิดหน่อยฮะ 🛠️ ลองส่งคำสั่งมาใหม่อีกทีน้า",
}

# ============================================================================
# EXAM DATES (Multi-date support)
# ============================================================================
EXAM_DATES = {
    "กลางภาค": [
        datetime.date(2026, 7, 13),
        datetime.date(2026, 7, 15),
        datetime.date(2026, 7, 17),
    ],
    "ปลายภาค": [
        datetime.date(2026, 9, 14),
        datetime.date(2026, 9, 16),
        datetime.date(2026, 9, 18),
    ]
}

# ============================================================================
# CLASS SCHEDULE
# ============================================================================
SCHEDULE = {
    0: [  # วันจันทร์
        {"start": "08:30", "end": "09:25", "subject": "ฟิสิกส์ (ครูจิราภรณ์)", "room": "335"},
        {"start": "09:25", "end": "10:20", "subject": "ฟิสิกส์ (ครูจิราภรณ์)", "room": "335"},
        {"start": "10:20", "end": "11:15", "subject": "คณิตเพิ่มเติม (ครูวรัญญา)", "room": "633"},
        {"start": "11:15", "end": "12:10", "subject": "คณิตเพิ่มเติม (ครูวรัญญา)", "room": "633"},
        {"start": "13:05", "end": "14:00", "subject": "อังกฤษพื้นฐาน (ครูเอื้อมเดือน)", "room": "633"},
        {"start": "14:00", "end": "14:55", "subject": "ภาษาไทย (ครูฉัฐรินทร์)", "room": "633"},
        {"start": "14:55", "end": "15:50", "subject": "คณิตพื้นฐาน (ครูพินธุ์สุดา)", "room": "633"},
    ],
    1: [  # วันอังคาร
        {"start": "08:30", "end": "09:25", "subject": "คณิตพื้นฐาน (ครูพินธุ์สุดา)", "room": "633"},
        {"start": "09:25", "end": "10:20", "subject": "อังกฤษพื้นฐาน (ครูเอื้อมเดือน)", "room": "633"},
        {"start": "10:20", "end": "11:15", "subject": "สังคมศึกษา (ครูณฐพร)", "room": "633"},
        {"start": "11:15", "end": "12:10", "subject": "แนะแนว (ครูขวัญพิลัสพัช)", "room": "633"},
        {"start": "13:05", "end": "14:00", "subject": "เคมี (ครูจิราภรณ์)", "room": "311"},
        {"start": "14:00", "end": "14:55", "subject": "ชีววิทยา (ครูศิริลักษณ์)", "room": "321"},
        {"start": "14:55", "end": "15:50", "subject": "คณิตเพิ่มพูน (ครูวรัญญา)", "room": "633"},
        {"start": "15:50", "end": "16:45", "subject": "คณิตเพิ่มพูน (ครูวรัญญา)", "room": "633"},
    ],
    2: [  # วันพุธ
        {"start": "08:30", "end": "09:25", "subject": "ฟิสิกส์ (ครูจิราภรณ์)", "room": "331"},
        {"start": "09:25", "end": "10:20", "subject": "ฟิสิกส์ (ครูจิราภรณ์)", "room": "331"},
        {"start": "10:20", "end": "11:15", "subject": "อังกฤษเพิ่มเติม (ครูเอื้อมเดือน)", "room": "633"},
        {"start": "11:15", "end": "12:10", "subject": "คณิตเพิ่มเติม (ครูวรัญญา)", "room": "633"},
        {"start": "13:05", "end": "14:00", "subject": "โฮมรูม/ประชุม ม.5", "room": "-"},
        {"start": "14:00", "end": "14:55", "subject": "หน้าที่พลเมือง (ครูวรัญญา)", "room": "633"},
        {"start": "14:55", "end": "15:50", "subject": "กิจกรรม", "room": "-"},
    ],
    3: [  # วันพฤหัสบดี
        {"start": "08:30", "end": "09:25", "subject": "ภาษาไทย (ครูฉัฐรินทร์)", "room": "633"},
        {"start": "09:25", "end": "10:20", "subject": "ประวัติศาสตร์ (ครูพงศ์พิชิต)", "room": "633"},
        {"start": "10:20", "end": "11:15", "subject": "คอมพิวเตอร์ (ครูเมกทัศน์)", "room": "216"},
        {"start": "11:15", "end": "12:10", "subject": "คอมพิวเตอร์ (ครูเมกทัศน์)", "room": "216"},
        {"start": "13:05", "end": "14:00", "subject": "คณิตเพิ่มพูน (ครูวรัญญา)", "room": "633"},
        {"start": "14:00", "end": "14:55", "subject": "คณิตเพิ่มพูน (ครูวรัญญา)", "room": "633"},
        {"start": "14:55", "end": "15:50", "subject": "สุข&พละ (ครูนรเศรษฐ์)", "room": "โดม3"},
        {"start": "15:50", "end": "16:45", "subject": "อังกฤษพื้นฐาน (ครูเอื้อมเดือน)", "room": "633"},
    ],
    4: [  # วันศุกร์
        {"start": "08:30", "end": "09:25", "subject": "ชีววิทยา (ครูศิริลักษณ์)", "room": "321"},
        {"start": "09:25", "end": "10:20", "subject": "ชีววิทยา (ครูศิริลักษณ์)", "room": "321"},
        {"start": "10:20", "end": "11:15", "subject": "สังคมศึกษา (ครูณฐพร)", "room": "633"},
        {"start": "11:15", "end": "12:10", "subject": "คณิตเพิ่มเติม (ครูวรัญญา)", "room": "633"},
        {"start": "13:05", "end": "14:00", "subject": "ดนตรี (ครูอภิชาต)", "room": "573"},
        {"start": "14:00", "end": "14:55", "subject": "เคมี (ครูจิราภรณ์)", "room": "311"},
        {"start": "14:55", "end": "15:50", "subject": "เคมี (ครูจิราภรณ์)", "room": "311"},
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