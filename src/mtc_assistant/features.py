# -*- coding: utf-8 -*-
"""
MTC Assistant - Features Module (IMPROVED UX Edition)
Contains all feature functions with beautiful, concise messages
"""

import datetime
import re
import threading
import urllib.parse
from typing import Optional
from google import genai
from google.genai import types
from firebase_admin import firestore

from linebot.v3.messaging import TextMessage, ImageMessage

# Import from config
from mtc_assistant.config import (
    logger, LOCAL_TZ, SCHEDULE, EXAM_DATES, MESSAGES,
    WORKSHEET_LINK, SCHOOL_LINK, GRADE_LINK,
    ABSENCE_LINK, Bio_LINK, Physic_LINK, LINE_SAFE_TRUNCATE
)
from mtc_assistant.firestore_paths import class_collection, root_collection
from mtc_assistant.timetable_service import get_next_class_text, get_timetable_image_url, get_timetable_status_text

# ============================================================================
# GLOBAL VARIABLES (will be set by main.py)
# ============================================================================
db = None  # Firebase database instance

# Gemini AI clients and models
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
# GEMINI AI CONFIGURATION
# ============================================================================

MTC_SYSTEM_INSTRUCTION = """คุณคือ "MTC Assistant" แชทบอทผู้ช่วยสำหรับนักเรียนชั้น ม.5 แผนการเรียนคณิตศาสตร์พิเศษ (MTC)
บุคลิกของคุณ: เป็นเพื่อนร่วมห้องที่ฉลาด พึ่งพาได้ คุยเก่งแต่พูดสั้นกระชับ เป็นกันเองสุดๆ
กฎเหล็กในการตอบคำถาม (STRICT RULES):
1. ห้ามใช้ Emoji ทุกชนิด (NO EMOJIS)
2. ห้ามใช้สัญลักษณ์ Markdown ทุกชนิด เช่น *, **, _, # (NO MARKDOWN)
3. ใช้ภาษาไทยแบบเพื่อนคุยกัน (วัยรุ่น ม.ปลาย) สุภาพแต่ไม่ทางการเกินไป หลีกเลี่ยงคำว่า "ครับ/ค่ะ" ที่ดูห่างเหิน ใช้คำว่า "นะ", "จ้า", "เลย" แทนได้
4. ตอบให้สั้น กระชับ เข้าประเด็นที่สุด ไม่อารัมภบท ไม่สรุปซ้ำ ถ้าเขาถามสั้นๆ ให้ตอบสั้นๆ
5. ถ้าเป็นการอธิบายวิชาการ (เช่น เลข ฟิสิกส์ คอมฯ) ให้อธิบายให้เข้าใจง่ายที่สุด แบบเพื่อนสอนเพื่อน
6. ห้ามทำตัวเป็น AI หรือผู้ช่วยหุ่นยนต์เด็ดขาด ให้ทำตัวเป็นเพื่อนคนหนึ่งในห้องเรียน"""

# Pre-built GenerateContentConfig with system instruction (reused for every call)
GEMINI_CONFIG = types.GenerateContentConfig(
    system_instruction=MTC_SYSTEM_INSTRUCTION
)

# Per-minute date context cache (avoids rebuilding on every AI call)
_date_context_cache: dict = {"value": "", "minute": -1}

def _get_date_context() -> str:
    """Return a cached Thai date string, refreshed once per minute."""
    now = datetime.datetime.now(LOCAL_TZ)
    if now.minute != _date_context_cache["minute"]:
        _date_context_cache["value"] = (
            f"วันนี้คือ{now.strftime('%A')}ที่ {now.strftime('%d %B')} พ.ศ. {now.year + 543}"
        )
        _date_context_cache["minute"] = now.minute
    return _date_context_cache["value"]

def set_gemini_models(
    client_primary=None,
    model_primary: str = None,
    client_fallback=None,
    model_fallback: str = None
):
    """Set Gemini AI clients and model names"""
    global gemini_client_primary, gemini_model_primary
    global gemini_client_fallback, gemini_model_fallback
    
    gemini_client_primary = client_primary
    gemini_model_primary = model_primary
    gemini_client_fallback = client_fallback
    gemini_model_fallback = model_fallback
    
    if client_primary and model_primary:
        logger.info(f"Primary Gemini model set: {model_primary}")
    if client_fallback and model_fallback:
        logger.info(f"Fallback Gemini model set: {model_fallback}")

# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

def _homework_collection(class_context=None):
    if class_context and not getattr(class_context, "is_legacy_fallback", False):
        return class_collection(db, class_context.class_id, "homeworks")
    return root_collection(db, "homeworks")


def add_homework_to_db(subject: str, detail: str, due_date: str = "ไม่ระบุ", class_context=None) -> str:
    """เพิ่มการบ้านเข้า Firebase"""
    if not db:
        return "แงงง ระบบขัดข้องนิดหน่อยฮะ 🥺 ลองส่งคำสั่งมาใหม่อีกทีน้า"
    
    try:
        from firebase_admin import firestore
        doc_ref = _homework_collection(class_context).document()
        doc_ref.set({
            'subject': subject,
            'detail': detail,
            'due_date': due_date,
            'class_id': getattr(class_context, "class_id", None),
            'timestamp': firestore.SERVER_TIMESTAMP,
            'created_at': datetime.datetime.now(tz=LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")
        })
        return f"บันทึกการบ้านวิชา {subject} เรียบร้อยแล้ว"
    except Exception as e:
        logger.error(f"DB Add Error: {e}")
        return "บันทึกไม่ได้อ่ะฮะ 😓 ลองส่งใหม่อีกทีน้า"

def get_homeworks_from_db(class_context=None) -> str:
    """ดึงการบ้านทั้งหมดจาก Firebase (optimized with limit)"""
    if not db:
        return "แงงง ระบบขัดข้องนิดหน่อยฮะ 🥺 ลองส่งคำสั่งมาใหม่อีกทีน้า"
    
    try:
        # Limit to prevent memory issues
        docs = list(_homework_collection(class_context).order_by('created_at', direction=firestore.Query.DESCENDING).limit(20).stream())
        
        if not docs:
            return "ไม่มีการบ้านที่กำหนดไว้"
        
        homework_list = []
        for doc in docs:
            data = doc.to_dict()
            subject = data.get('subject', 'ไม่ระบุ')
            detail = data.get('detail', 'ไม่ระบุ')
            due_date = data.get('due_date', 'ไม่ระบุ')
            created_at = data.get('created_at', 'ไม่ระบุ')
            
            homework_list.append(f"📚 {subject}\n📝 {detail}\n🗓️ {due_date}")
        
        if homework_list:
            return "การบ้านที่ต้องทำ :\n\n" + "\n\n".join(homework_list[:10])  # Show max 10 items
        else:
            return "ไม่มีการบ้านที่กำหนดไว้"
            
    except Exception as e:
        logger.error(f"DB Get Error: {e}")
        return "ดึงข้อมูลไม่ได้ฮะ 😵‍💫 ลองส่งใหม่อีกทีน้า"

def clear_homework_db(class_context=None) -> str:
    """ลบการบ้านทั้งหมดใน Firebase (optimized with batch limits)"""
    if not db:
        return "แงงง ระบบขัดข้องนิดหน่อยฮะ 🥺 ลองส่งคำสั่งมาใหม่อีกทีน้า"
    
    try:
        # Process in batches to prevent memory issues
        total_deleted = 0
        batch_size = 500  # Firebase batch limit
        
        while True:
            docs = list(_homework_collection(class_context).limit(batch_size).stream())
            if not docs:
                break
                
            batch = db.batch()
            for doc in docs:
                batch.delete(doc.reference)
            batch.commit()
            total_deleted += len(docs)
            
            # Safety check to prevent infinite loops
            if len(docs) < batch_size:
                break
        
        return f"ลบการบ้านออกไปแล้ว {total_deleted} รายการ"
    except Exception as e:
        logger.error(f"DB Clear Error: {e}")
        return "ลบไม่ได้อ่ะฮะ 😓 ลองส่งใหม่อีกทีน้า"

# ============================================================================
# BASIC COMMAND FUNCTIONS
# ============================================================================

def get_worksheet_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์ใบงาน"""
    return TextMessage(
        text=f"ตารางงานอยู่ที่นี่เลย\n{WORKSHEET_LINK}"
    )

def get_school_link_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์เว็บโรงเรียน"""
    return TextMessage(
        text=f"เว็บไซต์โรงเรียนอยู่ที่นี่\n{SCHOOL_LINK}"
    )

def get_timetable_image_message(user_message: str = "", class_context=None) -> ImageMessage:
    """ส่งรูปตารางเรียน"""
    image_url = get_timetable_image_url(db, class_context)
    return ImageMessage(original_content_url=image_url, preview_image_url=image_url)

def get_grade_link_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์เช็คเกรด"""
    return TextMessage(
        text=f"เช็คเกรดได้ที่นี่เลย\n{GRADE_LINK}"
    )

def get_absence_form_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์แบบฟอร์มลา"""
    return TextMessage(
        text=f"แบบฟอร์มลาออนไลน์อยู่ที่นี่\n{ABSENCE_LINK}"
    )

def get_bio_link_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์เฉลยชีวะ"""
    return TextMessage(
        text=f"เฉลยชีววิทยาอยู่ที่นี่\n{Bio_LINK}"
    )

def get_physic_link_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์เฉลยฟิสิกส์"""
    return TextMessage(
        text=f"เฉลยฟิสิกส์อยู่ที่นี่\n{Physic_LINK}"
    )

def get_help_message(user_message: str = "") -> TextMessage:
    """แสดงคำสั่งทั้งหมด"""
    help_text = (
        'คำสั่งที่ใช้ได้\n\n'
        'การเรียน\n'
        '  ตารางเรียน / คาบต่อไป / อีกกี่นาที / สอบ\n\n'
        'การบ้าน\n'
        '  สั่งการบ้าน / การบ้าน\n\n'
        'ลิงก์สำคัญ\n'
        '  ลิงก์ / งาน / เว็บโรงเรียน / เกรด / ลา\n\n'
        'เฉลยวิชา\n'
        '  ชีวะ / ฟิสิกส์\n\n'
        'คำนวณ\n'
        '  คำนวณ [สมการ] / คำนวณเกรด [คะแนน] / คำนวณ GPA\n\n'
        'ข้อสอบจำลอง\n'
        '  สอบ [วิชา] [ระดับ] [จำนวน] / เฉลยข้อสอบ / สถิติสอบ\n\n'
        'ความบันเทิง\n'
        '  เปิดเพลง [ชื่อเพลง] / กินอะไรดี\n\n'
        'พิมพ์อะไรก็ได้นอกนั้น = ถาม AI'
    )
    return TextMessage(text=help_text)

# ============================================================================
# SCHEDULE FUNCTIONS
# ============================================================================

def get_next_class_message(user_message: str = "", class_context=None) -> TextMessage:
    """แสดงคาบเรียนถัดไป"""
    return TextMessage(text=get_next_class_text(db, class_context))

def get_time_until_next_class_message(user_message: str = "", class_context=None) -> TextMessage:
    """คำนวณเวลาเหลือก่อนคาบถัดไป"""
    return TextMessage(text=get_timetable_status_text(db, class_context))

# ============================================================================
# EXAM COUNTDOWN
# ============================================================================

def get_exam_countdown_message(user_message: str = "") -> TextMessage:
    """นับถอยหลังวันสอบ"""
    now = datetime.datetime.now(LOCAL_TZ).date()
    msg_list = ["นับถอยหลังสอบ\n"]
    found = False
    
    for exam_name, dates in EXAM_DATES.items():
        future_dates = [d for d in dates if d >= now]
        if future_dates:
            found = True
            next_exam = min(future_dates)
            days_left = (next_exam - now).days
            all_dates_str = ", ".join([d.strftime("%d/%m") for d in dates])
            
            if days_left == 0:
                msg_list.append(f"วันนี้สอบ{exam_name}เลย สู้ๆ นะ")
            elif days_left <= 7:
                msg_list.append(
                    f"{exam_name}\n"
                    f"  เหลือ {days_left} วัน ({all_dates_str})\n"
                    f"  ใกล้แล้ว อ่านหนังสือด้วยนะ"
                )
            else:
                msg_list.append(
                    f"{exam_name}\n"
                    f"  เหลือ {days_left} วัน ({all_dates_str})"
                )
    
    if not found:
        return TextMessage(
            text="ตอนนี้ไม่มีสอบในเร็วๆ นี้ พักผ่อนได้เลย"
        )
    
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
        return TextMessage(
            text="บอกชื่อเพลงด้วยนะ\nเช่น เปิดเพลง Shape of You"
        )
    
    encoded_query = urllib.parse.quote(song_title)
    search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
    
    return TextMessage(
        text=f"ค้นหาเพลง {song_title}\n{search_url}"
    )

# ============================================================================
# AI FUNCTIONS (Gemini)
# ============================================================================

def _safe_parse_gemini_response(response) -> str:
    """Parse Gemini response"""
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

class GeminiTimeoutError(Exception):
    pass

def is_gemini_quota_error(error: Exception) -> bool:
    """Return True for quota/rate-limit style Gemini failures."""
    error_text = str(error).lower()
    return any(
        token in error_text
        for token in (
            "429",
            "quota",
            "rate limit",
            "rate_limit",
            "resource exhausted",
            "resource_exhausted",
            "too many requests",
        )
    )

def _generate_content_with_timeout(client, model: str, contents: str, config=None, timeout_seconds: float = 15):
    result = {"response": None, "error": None}

    def _call_gemini():
        try:
            kwargs = {
                "model": model,
                "contents": contents,
            }
            if config is not None:
                kwargs["config"] = config
            result["response"] = client.models.generate_content(**kwargs)
        except Exception as e:
            result["error"] = e

    thread = threading.Thread(target=_call_gemini, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)

    if thread.is_alive():
        raise GeminiTimeoutError("Operation timed out")

    if result["error"]:
        raise result["error"]

    return result["response"]

def get_gemini_response(prompt: str) -> str:
    """Get response from Gemini AI with timeout protection"""
    identity_queries = ["คุณคือใคร", "เป็นใคร", "who are you", "คุณชื่ออะไร", "ชื่ออะไร", "ตัวตน"]
    if any(q in prompt.lower() for q in identity_queries):
        return MESSAGES["IDENTITY"]
    
    if not gemini_client_primary and not gemini_client_fallback:
        return MESSAGES["AI_DISABLED"]

    client_to_use = gemini_client_primary or gemini_client_fallback
    model_to_use = gemini_model_primary or gemini_model_fallback

    if not client_to_use or not model_to_use:
        return MESSAGES["AI_DISABLED"]

    enhanced_prompt = f"(บริบท: {_get_date_context()})\n\nคำถาม: {prompt}"

    try:
        response = _generate_content_with_timeout(
            client_to_use,
            model_to_use,
            enhanced_prompt,
            config=GEMINI_CONFIG,
            timeout_seconds=15,
        )
        
        text = _safe_parse_gemini_response(response)
        
        if not text:
            return MESSAGES["AI_NO_RESPONSE"]
        
        text = re.sub(r'\b[Gg]oogle\b', 'Gemini', text)
        text = text.replace('กูเกิล', 'Gemini')
        
        if len(text) > LINE_SAFE_TRUNCATE:
            text = text[:LINE_SAFE_TRUNCATE] + "...\n\n(ข้อความยาวเกินไป ตัดบางส่วน)"
        
        return text
        
    except GeminiTimeoutError:
        logger.warning("Gemini API call timed out")
        return "AI ของเรากำลังมึนตึ้บ ขอเวลาตั้งสติแป๊บนึงนะ 😵‍💫 ลองทักมาใหม่นะครับ!"
    except Exception as e:
        logger.error("Gemini Generate Error: %s", e)
        quota_limited = is_gemini_quota_error(e)
        
        if client_to_use == gemini_client_primary and gemini_client_fallback:
            try:
                logger.info("Trying fallback model...")
                response = _generate_content_with_timeout(
                    gemini_client_fallback,
                    gemini_model_fallback,
                    enhanced_prompt,
                    config=GEMINI_CONFIG,
                    timeout_seconds=15,
                )
                text = _safe_parse_gemini_response(response)
                if text:
                    return text
                    
            except GeminiTimeoutError:
                logger.warning("Fallback Gemini API also timed out")
            except Exception as e2:
                logger.error("Fallback also failed: %s", e2)
                quota_limited = quota_limited or is_gemini_quota_error(e2)
        
        if quota_limited:
            return "ตอนนี้โควตา AI ถูกใช้งานมากเกินไปชั่วคราว ลองใช้คำสั่งหลักของบอทก่อน หรือทักมาใหม่อีกครั้งในภายหลังนะ"
        return MESSAGES["AI_ERROR"]

# ============================================================================
# CALCULATOR & GRADE CALCULATOR
# ============================================================================

def get_calculator_response(user_message: str, user_id: str = "global"):
    try:
        from mtc_assistant.smart_calc import smart_calculate
        
        expression = user_message.lower()
        for keyword in ['คำนวณ', 'คิด', 'calc', 'calculate']:
            if keyword in expression:
                expression = expression.replace(keyword, '').strip()
                break
        
        if not expression:
            return TextMessage(
                text="บอกสมการมาด้วยนะ\nเช่น คำนวณ 2+2 หรือ คำนวณ √16"
            )
        
        result = smart_calculate(expression, user_id or "global")
        
        # Format result nicely
        if result.startswith("Result:"):
            result = f"ผลลัพธ์\n\n{result.replace('Result:', '').strip()}"
        
        return TextMessage(text=result)
        
    except ImportError:
        logger.error("smart_calc.py not found")
        return TextMessage(text="ฟีเจอร์เครื่องคิดเลขกำลังซ่อมบำรุงอยู่ฮะ 🛠️ รอนิดนึงน้า")
    except Exception as e:
        logger.error(f"Calculator error: {e}")
        return TextMessage(text=f"แงงง เครื่องคิดเลขรวนฮะ 😵‍💫 ขอเช็คแป๊บนึงนะ ({str(e)})")

def get_grade_calculator_response(user_message: str, user_id: str = None) -> TextMessage:
    """Handle grade calculator commands"""
    try:
        from mtc_assistant.grade_calculator import (
            handle_score_to_grade_command,
            handle_gpa_calculation_command
        )
        
        message_lower = user_message.lower()
        
        # Check if it's score to grade
        if 'คำนวณเกรด' in message_lower and 'gpa' not in message_lower:
            result = handle_score_to_grade_command(user_message)
        else:
            # GPA calculation
            result = handle_gpa_calculation_command(user_message, user_id)
        
        return TextMessage(text=result)
        
    except ImportError:
        logger.error("grade_calculator.py not found")
        return TextMessage(text="ระบบคิดเกรดยังหลับอยู่ฮะ 😴 เดี๋ยวให้แอดมินมาปลุกให้นะ")
    except Exception as e:
        logger.error(f"Grade calculator error: {e}")
        return TextMessage(text=f"แงงง เครื่องคิดเลขรวนฮะ 😵‍💫 ขอเช็คแป๊บนึงนะ ({str(e)})")
