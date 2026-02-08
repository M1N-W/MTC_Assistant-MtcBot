# -*- coding: utf-8 -*-
"""
MTC Assistant - Features Module  
FIXED: Correct calculator import
"""

import datetime
import math
import re
import urllib.parse
from typing import Optional

from linebot.v3.messaging import TextMessage, ImageMessage

from config import (
    logger, LOCAL_TZ, SCHEDULE, EXAM_DATES, MESSAGES,
    WORKSHEET_LINK, SCHOOL_LINK, TIMETABLE_IMG, GRADE_LINK,
    ABSENCE_LINK, Bio_LINK, Physic_LINK, LINE_SAFE_TRUNCATE
)

db = None
gemini_client_primary = None
gemini_model_name_primary = None
gemini_client_fallback = None
gemini_model_name_fallback = None

def set_database(database) -> None:
    global db
    db = database

def add_homework_to_db(subject: str, detail: str, due_date: str = "ไม่ระบุ") -> str:
    if not db:
        return "⚠️ ระบบฐานข้อมูลยังไม่พร้อม"
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
        return f"✅ เพิ่มการบ้านวิชา '{subject}' สำเร็จ!"
    except Exception as e:
        logger.error(f"DB Add Error: {e}")
        return "❌ เกิดข้อผิดพลาด"

def get_homeworks_from_db() -> str:
    if not db:
        return "⚠️ ระบบฐานข้อมูลยังไม่พร้อม"
    try:
        from firebase_admin import firestore
        docs = db.collection('homeworks').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
        hw_list = []
        for doc in docs:
            d = doc.to_dict()
            hw_list.append(
                f"📚 *{d.get('subject', 'ไม่ระบุ')}*\n"
                f"📝 {d.get('detail', 'ไม่มี')}\n"
                f"📅 ส่ง: {d.get('due_date', 'ไม่ระบุ')}\n"
                f"(ID: {doc.id[-4:]})"
            )
        if not hw_list:
            return "🎉 ไม่มีการบ้าน"
        return "📋 *รายการการบ้าน*\n\n" + "\n" + "-" * 30 + "\n".join(hw_list)
    except Exception as e:
        logger.error(f"DB Get Error: {e}")
        return "❌ ข้อผิดพลาด"

def clear_homework_db() -> str:
    if not db:
        return "⚠️ ระบบฐานข้อมูลยังไม่พร้อม"
    try:
        docs = db.collection('homeworks').stream()
        count = 0
        for doc in docs:
            doc.reference.delete()
            count += 1
        return f"🗑️ ลบ {count} รายการ"
    except Exception as e:
        logger.error(f"DB Clear Error: {e}")
        return "❌ ข้อผิดพลาด"

def get_worksheet_message(user_message: str = "") -> TextMessage:
    return TextMessage(text=f"📝 ตารางงาน {WORKSHEET_LINK}")

def get_school_link_message(user_message: str = "") -> TextMessage:
    return TextMessage(text=f"🏫 เว็บโรงเรียน {SCHOOL_LINK}")

def get_timetable_image_message(user_message: str = "") -> ImageMessage:
    return ImageMessage(original_content_url=TIMETABLE_IMG, preview_image_url=TIMETABLE_IMG)

def get_grade_link_message(user_message: str = "") -> TextMessage:
    return TextMessage(text=f"📊 เช็คเกรด {GRADE_LINK}")

def get_absence_form_message(user_message: str = "") -> TextMessage:
    return TextMessage(text=f"📝 แบบฟอร์มลา {ABSENCE_LINK}")

def get_bio_link_message(user_message: str = "") -> TextMessage:
    return TextMessage(text=f"🧬 เฉลยชีวะ {Bio_LINK}")

def get_physic_link_message(user_message: str = "") -> TextMessage:
    return TextMessage(text=f"⚛️ เฉลยฟิสิกส์ {Physic_LINK}")

def get_help_message(user_message: str = "") -> TextMessage:
    help_text = (
        '📖 คำสั่งทั้งหมด\n\n'
        '📋 พื้นฐาน\n'
        '- งาน/การบ้าน, เว็บโรงเรียน, ตารางเรียน\n'
        '- เกรด, คาบต่อไป, ลา, สอบ\n\n'
        '🧪 เฉลย\n'
        '- ชีวะ, ฟิสิกส์\n\n'
        '🧮 คิดเลข\n'
        '- คำนวณ [สมการ]\n'
        '  ตัวอย่าง: คำนวณ 12*(5+3)^2\n\n'
        '🎓 คำนวณเกรด\n'
        '- คำนวณเกรด [คะแนน]\n'
        '  ตัวอย่าง: คำนวณเกรด 85\n'
        '- คำนวณ GPA [วิชา] [หน่วยกิต] [เกรด]\n'
        '  ตัวอย่าง: คำนวณ GPA คณิต 3 4 ฟิสิกส์ 3 3.5\n\n'
        '🎵 เพลง\n'
        '- เปิดเพลง [ชื่อ]\n\n'
        '💾 การบ้าน\n'
        '- สั่งการบ้าน | วิชา | รายละเอียด | วันส่ง\n'
        '- การบ้าน, ลบการบ้าน\n\n'
        '🤖 AI = พิมพ์ข้อความอื่นๆ'
    )
    return TextMessage(text=help_text)

def get_next_class_message(user_message: str = "") -> TextMessage:
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
                text=f"🔜 คาบต่อไป: {period['subject']}\n"
                     f"📍 ห้อง: {period['room']}\n"
                     f"⏰ {period['start']} - {period['end']}"
            )
        if start_time <= current_time < end_time:
            return TextMessage(
                text=f"⏳ กำลังเรียน: {period['subject']}\n"
                     f"📍 ห้อง: {period['room']}\n"
                     f"⏰ จนถึง: {period['end']}"
            )
    return TextMessage(text=MESSAGES["NO_CLASS_LEFT"])

def get_time_until_next_class_message(user_message: str = "") -> TextMessage:
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
            return TextMessage(text="ไม่มีคาบต่างจากปัจจุบัน")
    target_start_time = datetime.datetime.strptime(target["start"], "%H:%M").time()
    today = datetime.datetime.now(LOCAL_TZ).date()
    target_dt = datetime.datetime.combine(today, target_start_time, tzinfo=LOCAL_TZ)
    delta_seconds = (target_dt - now).total_seconds()
    minutes_left = max(0, math.ceil(delta_seconds / 60))
    minutes_text = "น้อยกว่า 1 นาที" if minutes_left == 0 else f"{minutes_left} นาที"
    return TextMessage(
        text=f"⏰ เหลือ {minutes_text}\n"
             f"🔜 {target['subject']}\n"
             f"📍 ห้อง: {target['room']}"
    )

def get_exam_countdown_message(user_message: str = "") -> TextMessage:
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
                    f"   ({all_dates_str})"
                )
    if not found:
        return TextMessage(text="🎉 ยังไม่มีสอบ!")
    return TextMessage(text="\n\n".join(msg_list))

def extract_youtube_id(url_or_text: str) -> Optional[str]:
    m = re.search(r'(?:v=|\/v\/|youtu\.be\/|\/embed\/)([A-Za-z0-9_\-]{11})', url_or_text)
    if m:
        return m.group(1)
    m2 = re.match(r'^[A-Za-z0-9_\-]{11}$', url_or_text.strip())
    if m2:
        return url_or_text.strip()
    return None

def get_music_link_message(user_message: str) -> TextMessage:
    music_keywords = ["เปิดเพลง", "หาเพลง", "ขอเพลง"]
    song_title = user_message.lower()
    for keyword in music_keywords:
        if keyword in song_title:
            song_title = song_title.replace(keyword, "").strip()
            break
    if not song_title:
        return TextMessage(text="กรุณาระบุชื่อเพลง")
    encoded_query = urllib.parse.quote(song_title)
    search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
    return TextMessage(
        text=f"🎵 ค้นหา: {song_title}\n"
             f"👉 {search_url}"
    )

def set_gemini_models(client_primary=None, model_primary: str = None, client_fallback=None, model_fallback: str = None) -> None:
    global gemini_client_primary, gemini_model_name_primary
    global gemini_client_fallback, gemini_model_name_fallback
    gemini_client_primary = client_primary
    gemini_model_name_primary = model_primary
    gemini_client_fallback = client_fallback
    gemini_model_name_fallback = model_fallback
    if client_primary and model_primary:
        logger.info(f"✅ Primary Gemini: {model_primary}")
    if client_fallback and model_fallback:
        logger.info(f"✅ Fallback Gemini: {model_fallback}")

def _safe_parse_gemini_response(response_obj) -> str:
    try:
        if response_obj is None:
            return ""
        if hasattr(response_obj, "text") and response_obj.text:
            return str(response_obj.text).strip()
        if hasattr(response_obj, "candidates") and response_obj.candidates:
            first_candidate = response_obj.candidates[0]
            if hasattr(first_candidate, "content") and first_candidate.content:
                content = first_candidate.content
                if hasattr(content, "parts") and content.parts:
                    for part in content.parts:
                        if hasattr(part, "text") and part.text:
                            return str(part.text).strip()
        return str(response_obj)
    except Exception as e:
        logger.error("Parse error: %s", e)
        return ""

def get_gemini_response(prompt: str) -> str:
    identity_queries = ["คุณคือใคร", "เป็นใคร", "who are you", "คุณชื่ออะไร", "ชื่ออะไร", "ตัวตน"]
    if any(q in prompt.lower() for q in identity_queries):
        return MESSAGES["IDENTITY"]
    if not gemini_client_primary and not gemini_client_fallback:
        return MESSAGES["AI_DISABLED"]
    now = datetime.datetime.now(LOCAL_TZ)
    date_context = f"วันนี้คือ{now.strftime('%A')}ที่ {now.strftime('%d %B')} พ.ศ. {now.year + 543}"
    enhanced_prompt = f"(บริบท: {date_context})\n\nคำถาม: {prompt}"
    if gemini_client_primary and gemini_model_name_primary:
        try:
            response = gemini_client_primary.models.generate_content(
                model=gemini_model_name_primary,
                contents=enhanced_prompt
            )
            text = _safe_parse_gemini_response(response)
            if text:
                text = re.sub(r'\b[Gg]oogle\b', 'Gemini', text)
                text = text.replace('กูเกิล', 'Gemini')
                if len(text) > LINE_SAFE_TRUNCATE:
                    text = text[:LINE_SAFE_TRUNCATE] + "...\n\n(ตัดบางส่วน)"
                return text
        except Exception as e:
            logger.warning(f"Primary failed: {e}")
    if gemini_client_fallback and gemini_model_name_fallback:
        try:
            response = gemini_client_fallback.models.generate_content(
                model=gemini_model_name_fallback,
                contents=enhanced_prompt
            )
            text = _safe_parse_gemini_response(response)
            if text:
                text = re.sub(r'\b[Gg]oogle\b', 'Gemini', text)
                text = text.replace('กูเกิล', 'Gemini')
                if len(text) > LINE_SAFE_TRUNCATE:
                    text = text[:LINE_SAFE_TRUNCATE] + "...\n\n(ตัดบางส่วน)"
                return text
        except Exception as e:
            logger.error(f"Fallback failed: {e}")
            return MESSAGES["AI_ERROR"]
    return MESSAGES["AI_NO_RESPONSE"]

# FIXED: Use smart_calculate instead of calculate
def get_calculator_response(user_message: str) -> TextMessage:
    """Handle calculator command - FIXED"""
    try:
        from smart_calc import smart_calculate  # ✅ FIXED: Correct import
        
        expression = user_message
        prefixes = ["คำนวณ", "คิด", "calc", "calculate", "="]
        for prefix in prefixes:
            if expression.lower().startswith(prefix):
                expression = expression[len(prefix):].strip()
                break
        
        if not expression:
            help_text = (
                "🧮 *เครื่องคิดเลข*\n\n"
                "💡 วิธีใช้:\n"
                "• คำนวณ 12*(5+3)^2\n"
                "• คำนวณ sqrt(144) + sin(pi/2)\n"
                "• คำนวณ x = 5, x * 2\n"
                "• คำนวณ 50%, 5!\n\n"
                "🔢 ฟังก์ชัน: sin, cos, tan, sqrt, log, exp, abs, round, factorial\n"
                "📝 คำสั่ง: vars, clearvars"
            )
            return TextMessage(text=help_text)
        
        result = smart_calculate(expression)  # ✅ FIXED: Use smart_calculate
        return TextMessage(text=f"🧮 {result}")
        
    except ImportError:
        logger.error("smart_calc.py not found")
        return TextMessage(text="❌ ระบบคิดเลขไม่พร้อม")
    except Exception as e:
        logger.error(f"Calc error: {e}")
        return TextMessage(text=f"❌ ข้อผิดพลาด: {str(e)[:100]}")

def get_grade_calculator_response(user_message: str) -> TextMessage:
    """Handle grade calculator - returns TextMessage"""
    try:
        from grade_calculator import (
            handle_score_to_grade_command,
            handle_gpa_calculation_command
        )
        msg_lower = user_message.lower()
        if "gpa" in msg_lower or "เกรดเฉลี่ย" in msg_lower:
            result = handle_gpa_calculation_command(user_message)
        else:
            result = handle_score_to_grade_command(user_message)
        
        return TextMessage(text=result)  # ✅ FIXED: Return TextMessage
        
    except ImportError:
        logger.error("grade_calculator.py not found")
        return TextMessage(text="❌ ระบบคำนวณเกรดไม่พร้อม")
    except Exception as e:
        logger.error(f"Grade calc error: {e}")
        return TextMessage(text=f"❌ ข้อผิดพลาด: {str(e)[:100]}")

__all__ = [
    'set_database',
    'set_gemini_models',
    'add_homework_to_db',
    'get_homeworks_from_db',
    'clear_homework_db',
    'get_worksheet_message',
    'get_school_link_message',
    'get_timetable_image_message',
    'get_grade_link_message',
    'get_absence_form_message',
    'get_bio_link_message',
    'get_physic_link_message',
    'get_help_message',
    'get_next_class_message',
    'get_time_until_next_class_message',
    'get_exam_countdown_message',
    'get_music_link_message',
    'get_gemini_response',
    'get_calculator_response',  # ✅ Export
    'get_grade_calculator_response',  # ✅ Export
]
