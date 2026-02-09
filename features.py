# -*- coding: utf-8 -*-
"""
MTC Assistant - Features Module (FIXED for google-genai)
Contains all feature functions: schedule, homework, music, AI, etc.

FIXES:
1. Changed import from google.generativeai to google.genai
2. Added set_gemini_models() function (was set_gemini_model)
3. Updated get_gemini_response() to use google-genai client API
"""

import datetime
import math
import re
import urllib.parse
from typing import Optional
from google import genai  # ✅ FIXED: Changed from google.generativeai

from linebot.v3.messaging import TextMessage, ImageMessage

# Import from config
from config import (
    logger, LOCAL_TZ, SCHEDULE, EXAM_DATES, MESSAGES,
    WORKSHEET_LINK, SCHOOL_LINK, TIMETABLE_IMG, GRADE_LINK,
    ABSENCE_LINK, Bio_LINK, Physic_LINK, LINE_SAFE_TRUNCATE
)

# ============================================================================
# GLOBAL VARIABLES (will be set by main.py)
# ============================================================================
db = None  # Firebase database instance

# Gemini AI clients and models (NEW: support dual models)
gemini_client_primary = None
gemini_model_primary = None
gemini_client_fallback = None
gemini_model_fallback = None

# ============================================================================
# DATABASE FUNCTIONS (Firebase/Homework)
# ============================================================================

def set_database(database):
    """Set Firebase database instance"""
    global db
    db = database

# ============================================================================
# GEMINI AI CONFIGURATION (FIXED)
# ============================================================================

def set_gemini_models(
    client_primary=None,
    model_primary: str = None,
    client_fallback=None,
    model_fallback: str = None
):
    """
    Set Gemini AI clients and model names
    
    ✅ FIXED: New function to match main.py call
    
    Args:
        client_primary: Primary Gemini client (google.genai.Client)
        model_primary: Primary model name (e.g., 'gemini-3-flash-preview')
        client_fallback: Fallback Gemini client
        model_fallback: Fallback model name (e.g., 'gemini-2.5-flash-preview')
    """
    global gemini_client_primary, gemini_model_primary
    global gemini_client_fallback, gemini_model_fallback
    
    gemini_client_primary = client_primary
    gemini_model_primary = model_primary
    gemini_client_fallback = client_fallback
    gemini_model_fallback = model_fallback
    
    if client_primary and model_primary:
        logger.info(f"✅ Primary Gemini model set: {model_primary}")
    if client_fallback and model_fallback:
        logger.info(f"✅ Fallback Gemini model set: {model_fallback}")

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

def add_homework_to_db(subject: str, detail: str, due_date: str = "ไม่ระบุ") -> str:
    """เพิ่มการบ้านเข้า Firebase"""
    if not db:
        return "⚠️ ระบบฐานข้อมูลยังไม่พร้อม กรุณาติดต่อผู้ดูแลระบบ"
    
    try:
        from firebase_admin import firestore
        doc_ref = db.collection('homeworks').document()
        doc_ref.set({
            'subject': subject,
            'detail': detail,
            'due_date': due_date,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'created_at': datetime.datetime.now(tz=LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")
        })
        return f"✅ เพิ่มการบ้านวิชา '{subject}' สำเร็จแล้วครับ!"
    except Exception as e:
        logger.error(f"DB Add Error: {e}")
        return "❌ เกิดข้อผิดพลาดในการเพิ่มการบ้าน"

def get_homeworks_from_db() -> str:
    """ดึงรายการการบ้านจาก Firebase"""
    if not db:
        return "⚠️ ระบบฐานข้อมูลยังไม่พร้อมครับ"
    
    try:
        from firebase_admin import firestore
        docs = db.collection('homeworks').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
        hw_list = []
        for doc in docs:
            d = doc.to_dict()
            hw_list.append(
                f"📚 *{d.get('subject', 'ไม่ระบุ')}*\n"
                f"📝 {d.get('detail', 'ไม่มีรายละเอียด')}\n"
                f"📅 ส่ง: {d.get('due_date', 'ไม่ระบุ')}\n"
                f"(ID: {doc.id[-4:]})"
            )
        
        if not hw_list:
            return "🎉 เย้! ตอนนี้ไม่มีการบ้านค้างในระบบครับ"
        
        return "📋 *รายการการบ้านปัจจุบัน*\n\n" + "\n" + "-" * 30 + "\n".join(hw_list)
    except Exception as e:
        logger.error(f"DB Get Error: {e}")
        return "❌ เกิดข้อผิดพลาดในการดึงข้อมูลการบ้าน"

def clear_homework_db() -> str:
    """ลบการบ้านทั้งหมดใน Firebase"""
    if not db:
        return "⚠️ ระบบฐานข้อมูลยังไม่พร้อมครับ"
    
    try:
        docs = db.collection('homeworks').stream()
        count = 0
        for doc in docs:
            doc.reference.delete()
            count += 1
        
        return f"🗑️ ลบการบ้านทั้งหมดแล้ว ({count} รายการ)"
    except Exception as e:
        logger.error(f"DB Clear Error: {e}")
        return "❌ เกิดข้อผิดพลาดในการลบข้อมูล"

# ============================================================================
# BASIC COMMAND FUNCTIONS
# ============================================================================

def get_worksheet_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์ใบงาน"""
    return TextMessage(text=f"📝 ตารางงานอยู่นี่ครับ {WORKSHEET_LINK}")

def get_school_link_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์เว็บโรงเรียน"""
    return TextMessage(text=f"🏫 เว็บไซต์โรงเรียนครับ {SCHOOL_LINK}")

def get_timetable_image_message(user_message: str = "") -> ImageMessage:
    """ส่งรูปตารางเรียน"""
    return ImageMessage(original_content_url=TIMETABLE_IMG, preview_image_url=TIMETABLE_IMG)

def get_grade_link_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์เช็คเกรด"""
    return TextMessage(text=f"📊 เช็คเกรดได้ที่นี่ครับ {GRADE_LINK}")

def get_absence_form_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์แบบฟอร์มลา"""
    return TextMessage(text=f"📝 ลิงก์แจ้งลาครับ {ABSENCE_LINK}")

def get_bio_link_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์เฉลยชีวะ"""
    return TextMessage(text=f"🧬 เฉลยชีววิทยาครับ {Bio_LINK}")

def get_physic_link_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์เฉลยฟิสิกส์"""
    return TextMessage(text=f"⚛️ เฉลยฟิสิกส์ครับ {Physic_LINK}")

def get_help_message(user_message: str = "") -> TextMessage:
    """แสดงคำสั่งทั้งหมด"""
    help_text = (
        '📖 รายการคำสั่งทั้งหมด\n\n'
        '📋 คำสั่งพื้นฐาน\n'
        '- งาน / การบ้าน = ดูใบงาน\n'
        '- เว็บโรงเรียน = ลิงก์เว็บโรงเรียน\n'
        '- ตารางเรียน = ดูตารางเรียน\n'
        '- เกรด = เช็คเกรด\n'
        '- คาบต่อไป = ดูว่าเรียนอะไรต่อ\n'
        '- อีกกี่นาที = เช็คเวลาเหลือก่อนคาบถัดไป\n'
        '- ลา = แบบฟอร์มลา\n'
        '- สอบ = นับถอยหลังวันสอบ\n\n'
        '🧪 คำสั่งเฉลย\n'
        '- ชีวะ = เฉลยชีววิทยา\n'
        '- ฟิสิกส์ = เฉลยฟิสิกส์\n\n'
        '🧮 คิดเลข\n'
        '- คำนวณ [สมการ]\n'
        '  ตัวอย่าง: คำนวณ 12*(5+3)^2\n\n'
        '🎓 คำนวณเกรด\n'
        '- คำนวณเกรด [คะแนน]\n'
        '  ตัวอย่าง: คำนวณเกรด 85\n'
        '- คำนวณ GPA [วิชา] [หน่วยกิต] [เกรด]\n'
        '  ตัวอย่าง: คำนวณ GPA คณิต 3 4 ฟิสิกส์ 3 3.5\n\n'
        '📚 ข้อสอบจำลอง (🆕)\n'
        '- สอบ [วิชา] [ระดับ] [จำนวน]\n'
        '  ตัวอย่าง: สอบ คณิต ง่าย 5\n'
        '  วิชา: คณิต, ฟิสิกส์, เคมี, ชีวะ\n'
        '  ระดับ: ง่าย, กลาง, ยาก\n'
        '- เฉลยข้อสอบ = ดูเฉลยทั้งหมด\n'
        '- สถิติสอบ = ดูประวัติการสอบ\n\n'
        '🎵 ความบันเทิง\n'
        '- เปิดเพลง [ชื่อเพลง] = หาเพลงจาก YouTube\n\n'
        '💾 คำสั่งการบ้าน\n'
        '- สั่งการบ้าน | วิชา | รายละเอียด | วันส่ง\n'
        '  ตัวอย่าง: สั่งการบ้าน | ฟิสิกส์ | ทำแบบฝึกหัด 4.1 | วันศุกร์\n'
        '- การบ้าน / ดูการบ้าน = ดูการบ้านทั้งหมด\n'
        '- ลบการบ้านทั้งหมด = ล้างข้อมูล\n\n'
        '🤖 AI\n'
        '- พิมพ์ข้อความอื่นๆ = ตอบด้วย AI'
    )
    return TextMessage(text=help_text)

# ============================================================================
# SCHEDULE FUNCTIONS
# ============================================================================

def get_next_class_message(user_message: str = "") -> TextMessage:
    """แสดงคาบเรียนถัดไป"""
    now = datetime.datetime.now(LOCAL_TZ)
    day_idx = now.weekday()
    
    if day_idx not in SCHEDULE:
        return TextMessage(text=MESSAGES["NO_CLASS_TODAY"])
    
    current_time = now.time()
    periods = SCHEDULE[day_idx]
    
    for period in periods:
        start_time = datetime.datetime.strptime(period["start"], "%H:%M").time()
        end_time = datetime.datetime.strptime(period["end"], "%H:%M").time()
        
        if current_time < start_time:
            return TextMessage(
                text=f"🔜 คาบต่อไป : {period['subject']}\n"
                     f"📍 ห้อง : {period['room']}\n"
                     f"⏰ เวลา : {period['start']} - {period['end']}"
            )
        
        if start_time <= current_time < end_time:
            return TextMessage(
                text=f"⏳ กำลังเรียน : {period['subject']}\n"
                     f"📍 ห้อง : {period['room']}\n"
                     f"⏰ จนถึง : {period['end']}"
            )
    
    return TextMessage(text=MESSAGES["NO_CLASS_LEFT"])

def get_time_until_next_class_message(user_message: str = "") -> TextMessage:
    """คำนวณเวลาเหลือก่อนคาบถัดไป"""
    now = datetime.datetime.now(LOCAL_TZ)
    day_idx = now.weekday()
    
    if day_idx not in SCHEDULE:
        return TextMessage(text=MESSAGES["NO_CLASS_TODAY"])
    
    current_time = now.time()
    periods = SCHEDULE[day_idx]
    
    current_index = None
    for idx, period in enumerate(periods):
        start_t = datetime.datetime.strptime(period["start"], "%H:%M").time()
        end_t = datetime.datetime.strptime(period["end"], "%H:%M").time()
        if start_t <= current_time < end_t:
            current_index = idx
            break
    
    target = None
    if current_index is None:
        for period in periods:
            start_t = datetime.datetime.strptime(period["start"], "%H:%M").time()
            if current_time < start_t:
                target = period
                break
        
        if target is None:
            return TextMessage(text=MESSAGES["NO_CLASS_LEFT"])
    else:
        current_subject = periods[current_index]["subject"]
        for idx in range(current_index + 1, len(periods)):
            if periods[idx]["subject"] != current_subject:
                target = periods[idx]
                break
        
        if target is None:
            return TextMessage(text="วันนี้ไม่มีคาบเรียนที่ต่างจากคาบปัจจุบันอีกแล้วครับ")
    
    target_start_time = datetime.datetime.strptime(target["start"], "%H:%M").time()
    target_dt = datetime.datetime.combine(now.date(), target_start_time).replace(tzinfo=LOCAL_TZ)
    delta_seconds = (target_dt - now).total_seconds()
    minutes_left = max(0, math.ceil(delta_seconds / 60))
    
    minutes_text = "น้อยกว่า 1 นาที" if minutes_left == 0 else f"{minutes_left} นาที"
    
    return TextMessage(
        text=f"⏰ เหลือเวลาอีก {minutes_text}\n"
             f"🔜 คาบถัดไป : {target['subject']}\n"
             f"📍 ห้อง : {target['room']}"
    )

# ============================================================================
# EXAM COUNTDOWN
# ============================================================================

def get_exam_countdown_message(user_message: str = "") -> TextMessage:
    """นับถอยหลังวันสอบ"""
    now = datetime.datetime.now(LOCAL_TZ).date()
    msg_list = ["⏳ *นับถอยหลังสอบ*\n"]
    found = False
    
    for exam_name, dates in EXAM_DATES.items():
        future_dates = [d for d in dates if d >= now]
        if future_dates:
            found = True
            next_exam = min(future_dates)
            days_left = (next_exam - now).days
            all_dates_str = ", ".join([d.strftime("%d/%m") for d in dates])
            
            if days_left == 0:
                msg_list.append(f"🔥 วันนี้สอบ{exam_name}! สู้ๆ!")
            else:
                msg_list.append(
                    f"📌 {exam_name}\n"
                    f"   เหลือ {days_left} วัน\n"
                    f"   (สอบวันที่ {all_dates_str})"
                )
    
    if not found:
        return TextMessage(text="🎉 ยังไม่มีสอบเร็วๆ นี้ พักผ่อนได้!")
    
    return TextMessage(text="\n\n".join(msg_list))

# ============================================================================
# MUSIC SEARCH
# ============================================================================

def get_music_link_message(user_message: str) -> TextMessage:
    """หาเพลงจาก YouTube"""
    music_keywords = ["เปิดเพลง", "หาเพลง", "ขอเพลง"]
    song_title = user_message.lower()
    
    for keyword in music_keywords:
        if keyword in song_title:
            song_title = song_title.replace(keyword, "").strip()
            break
    
    if not song_title:
        return TextMessage(text="กรุณาระบุชื่อเพลงด้วยครับ เช่น 'เปิดเพลง never gonna give you up'")
    
    encoded_query = urllib.parse.quote(song_title)
    search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
    
    return TextMessage(
        text=f"🎵 ค้นหาเพลง: {song_title}\n"
             f"👉 {search_url}\n\n"
             f"💡 กดลิงก์เพื่อดูผลการค้นหาใน YouTube"
    )

# ============================================================================
# AI FUNCTIONS (Gemini) - ✅ FIXED for google-genai
# ============================================================================

def _safe_parse_gemini_response(response) -> str:
    """Parse Gemini response - ✅ FIXED for google-genai"""
    try:
        if response is None:
            return ""
        
        if hasattr(response, "text") and response.text:
            return str(response.text).strip()
        
        if hasattr(response, "candidates") and response.candidates:
            first_candidate = response.candidates[0]
            if hasattr(first_candidate, "content") and first_candidate.content:
                content = first_candidate.content
                if hasattr(content, "parts") and content.parts:
                    parts_text = []
                    for part in content.parts:
                        if hasattr(part, "text") and part.text:
                            parts_text.append(str(part.text))
                    if parts_text:
                        return "".join(parts_text).strip()
        
        return str(response)
    except Exception as e:
        logger.error("Error parsing Gemini response: %s", e)
        return ""

def get_gemini_response(prompt: str) -> str:
    """Get response from Gemini AI - ✅ FIXED for google-genai"""
    identity_queries = ["คุณคือใคร", "เป็นใคร", "who are you", "คุณชื่ออะไร", "ชื่ออะไร", "ตัวตน"]
    if any(q in prompt.lower() for q in identity_queries):
        return MESSAGES["IDENTITY"]
    
    if not gemini_client_primary and not gemini_client_fallback:
        return MESSAGES["AI_DISABLED"]
    
    try:
        now = datetime.datetime.now(LOCAL_TZ)
        date_context = f"วันนี้คือ{now.strftime('%A')}ที่ {now.strftime('%d %B')} พ.ศ. {now.year + 543}"
        enhanced_prompt = f"(บริบท: {date_context})\n\nคำถาม: {prompt}"
        
        client_to_use = gemini_client_primary or gemini_client_fallback
        model_to_use = gemini_model_primary or gemini_model_fallback
        
        if not client_to_use or not model_to_use:
            return MESSAGES["AI_DISABLED"]
        
        # ✅ FIXED: Use google-genai API
        response = client_to_use.models.generate_content(
            model=model_to_use,
            contents=enhanced_prompt
        )
        
        text = _safe_parse_gemini_response(response)
        
        if not text:
            return MESSAGES["AI_NO_RESPONSE"]
        
        text = re.sub(r'\b[Gg]oogle\b', 'Gemini', text)
        text = text.replace('กูเกิล', 'Gemini')
        
        if len(text) > LINE_SAFE_TRUNCATE:
            text = text[:LINE_SAFE_TRUNCATE] + "...\n\n(ข้อความยาวเกินไป ตัดบางส่วน)"
        
        return text
        
    except Exception as e:
        logger.error("Gemini Generate Error: %s", e)
        
        if client_to_use == gemini_client_primary and gemini_client_fallback:
            try:
                logger.info("Trying fallback model...")
                response = gemini_client_fallback.models.generate_content(
                    model=gemini_model_fallback,
                    contents=enhanced_prompt
                )
                text = _safe_parse_gemini_response(response)
                if text:
                    return text
            except Exception as e2:
                logger.error("Fallback also failed: %s", e2)
        
        return MESSAGES["AI_ERROR"]

# ============================================================================
# CALCULATOR & GRADE CALCULATOR
# ============================================================================

def get_calculator_response(user_message: str) -> TextMessage:
    """Handle calculator commands"""
    try:
        from smart_calc import smart_calculate
        
        expression = user_message.lower()
        for keyword in ['คำนวณ', 'คิด', 'calc', 'calculate']:
            if keyword in expression:
                expression = expression.replace(keyword, '').strip()
                break
        
        if not expression:
            return TextMessage(
                text="⚠️ กรุณาระบุสมการ\n"
                     "ตัวอย่าง: คำนวณ 2+2\n"
                     "         คำนวณ sqrt(16)\n"
                     "         คำนวณ x=5, x*2"
            )
        
        result = smart_calculate(expression)
        return TextMessage(text=result)
        
    except ImportError:
        logger.error("smart_calc.py not found")
        return TextMessage(text="❌ ระบบคำนวณยังไม่พร้อมใช้งาน")
    except Exception as e:
        logger.error(f"Calculator error: {e}")
        return TextMessage(text=f"❌ เกิดข้อผิดพลาด: {str(e)}")

def get_grade_calculator_response(user_message: str, user_id: str = None) -> TextMessage:
    """
    Handle grade calculator commands
    ✅ UPDATED: Now supports user_id for session-based GPA
    """
    try:
        from grade_calculator import (
            handle_score_to_grade_command,
            handle_gpa_calculation_command
        )
        
        message_lower = user_message.lower()
        
        # Check if it's score to grade (no user_id needed)
        if 'คำนวณเกรด' in message_lower and 'gpa' not in message_lower:
            result = handle_score_to_grade_command(user_message)
        else:
            # GPA calculation - pass user_id for session support
            result = handle_gpa_calculation_command(user_message, user_id)
        
        return TextMessage(text=result)
        
    except ImportError:
        logger.error("grade_calculator.py not found")
        return TextMessage(text="❌ ระบบคำนวณเกรดยังไม่พร้อมใช้งาน")
    except Exception as e:
        logger.error(f"Grade calculator error: {e}")
        return TextMessage(text=f"❌ เกิดข้อผิดพลาด: {str(e)}")
