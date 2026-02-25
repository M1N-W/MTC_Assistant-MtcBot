# -*- coding: utf-8 -*-
"""
MTC Assistant - Grade Calculator Feature (IMPROVED UX)
คำนวณเกรดและ GPA - รองรับหลายรูปแบบการป้อนข้อมูล

IMPROVEMENTS:
1. Support multiple input formats (pipe, comma, multi-line)
2. Session-based GPA calculation (add courses one by one)
3. Better error messages in Thai
4. Flexible parsing (forgiving of extra spaces)
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging
import re
import time

logger = logging.getLogger(__name__)

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Subject:
    """Subject with grade and credits"""
    name: str
    credits: float
    grade: str
    score: Optional[float] = None

# Grade to GPA mapping (MTC school system)
GRADE_TO_GPA = {
    "4": 4.0,
    "3.5": 3.5,
    "3": 3.0,
    "2.5": 2.5,
    "2": 2.0,
    "1.5": 1.5,
    "1": 1.0,
    "0": 0.0,
}

SCORE_TO_GRADE = [
    (80, 100,  "4"),
    (75,  79.99, "3.5"),
    (70,  74.99, "3"),
    (65,  69.99, "2.5"),
    (60,  64.99, "2"),
    (55,  59.99, "1.5"),
    (50,  54.99, "1"),
    (0,   49.99, "0"),
]

# ============================================================================
# SESSION MANAGER FOR MULTI-STEP GPA
# ============================================================================

_gpa_sessions: Dict[str, dict] = {}  # user_id -> {"subjects": [], "started": float}
_GPA_SESSION_TTL = 3600  # 1 hour

def _prune_stale_gpa_sessions():
    """Remove GPA sessions older than TTL to prevent memory leaks."""
    now = time.time()
    stale = [uid for uid, s in _gpa_sessions.items() if now - s.get("started", 0) > _GPA_SESSION_TTL]
    for uid in stale:
        del _gpa_sessions[uid]

def start_gpa_session(user_id: str) -> str:
    """Start new GPA calculation session"""
    _prune_stale_gpa_sessions()
    _gpa_sessions[user_id] = {"subjects": [], "started": time.time()}
    return (
        "เริ่มคำนวณ GPA แล้ว\n\n"
        "เพิ่มวิชาทีละวิชาได้เลย\n"
        "พิมพ์: เพิ่มวิชา [ชื่อ] [หน่วยกิต] [เกรด]\n"
        "เช่น: เพิ่มวิชา คณิต 3 4\n\n"
        "เสร็จแล้วพิมพ์: คำนวณ GPA\n"
        "ยกเลิกพิมพ์: ยกเลิก GPA"
    )

def add_subject_to_session(user_id: str, subject: Subject) -> str:
    """Add subject to user's GPA session"""
    if user_id not in _gpa_sessions:
        return "ยังไม่ได้เริ่มนะ พิมพ์ 'เริ่ม GPA' ก่อนได้เลย"
    
    _gpa_sessions[user_id]["subjects"].append(subject)
    count = len(_gpa_sessions[user_id]["subjects"])
    
    return (
        f"เพิ่ม {subject.name} แล้ว ({subject.credits} หน่วยกิต เกรด {subject.grade})\n"
        f"ตอนนี้มี {count} วิชา\n"
        f"พิมพ์ 'คำนวณ GPA' เมื่อเพิ่มครบแล้ว"
    )

def calculate_session_gpa(user_id: str) -> str:
    """Calculate GPA from session"""
    if user_id not in _gpa_sessions:
        return "ไม่พบข้อมูล GPA พิมพ์ 'เริ่ม GPA' เพื่อเริ่มใหม่ได้เลย"
    
    subjects = _gpa_sessions[user_id]["subjects"]
    
    if not subjects:
        return "ยังไม่มีวิชาเลยนะ พิมพ์ 'เพิ่มวิชา [ชื่อ] [หน่วยกิต] [เกรด]' เพื่อเพิ่ม"
    
    gpa, details = calculate_gpa(subjects)
    result = format_gpa_result(gpa, details)
    
    # Clear session after calculation
    del _gpa_sessions[user_id]
    
    return result

def cancel_gpa_session(user_id: str) -> str:
    """Cancel GPA session"""
    _prune_stale_gpa_sessions()
    if user_id in _gpa_sessions:
        del _gpa_sessions[user_id]
        return "ยกเลิกการคำนวณ GPA แล้ว"
    return "ไม่มี session ที่จะยกเลิกนะ"

def show_session_status(user_id: str) -> str:
    """Show current session subjects"""
    if user_id not in _gpa_sessions:
        return "ยังไม่ได้เริ่มนะ พิมพ์ 'เริ่ม GPA' เพื่อเริ่มได้เลย"
    
    subjects = _gpa_sessions[user_id]["subjects"]
    
    if not subjects:
        return "ยังไม่มีวิชาในรายการ พิมพ์ 'เพิ่มวิชา [ชื่อ] [หน่วยกิต] [เกรด]' เพื่อเพิ่ม"
    
    msg = f"วิชาที่เพิ่มไว้แล้ว ({len(subjects)} วิชา)\n\n"
    
    for i, subj in enumerate(subjects, 1):
        msg += f"{i}. {subj.name}\n"
        msg += f"   {subj.credits} หน่วยกิต, เกรด {subj.grade}\n\n"
    
    msg += "พิมพ์ 'คำนวณ GPA' เพื่อดูผล"
    
    return msg

# ============================================================================
# CORE FUNCTIONS
# ============================================================================

def score_to_grade(score: float) -> str:
    """Convert score to grade"""
    if not (0 <= score <= 100):
        raise ValueError("คะแนนต้องอยู่ระหว่าง 0-100")
    
    for (min_score, max_score, grade) in SCORE_TO_GRADE:
        if min_score <= score <= max_score:
            return grade
    
    return "0"

def calculate_gpa(subjects: List[Subject]) -> Tuple[float, Dict]:
    """Calculate GPA from list of subjects"""
    if not subjects:
        return 0.0, {"error": "ไม่มีวิชาในระบบ"}
    
    total_credits = 0.0
    total_grade_points = 0.0
    invalid_subjects = []
    
    for subject in subjects:
        if subject.grade not in GRADE_TO_GPA:
            invalid_subjects.append(subject.name)
            continue
        
        gpa_value = GRADE_TO_GPA[subject.grade]
        grade_points = gpa_value * subject.credits
        
        total_credits += subject.credits
        total_grade_points += grade_points
    
    if total_credits == 0:
        return 0.0, {
            "error": "ไม่มีหน่วยกิตที่ถูกต้อง",
            "invalid_subjects": invalid_subjects
        }
    
    gpa = total_grade_points / total_credits
    
    details = {
        "gpa": round(gpa, 2),
        "total_credits": total_credits,
        "total_grade_points": total_grade_points,
        "subject_count": len(subjects),
        "invalid_subjects": invalid_subjects
    }
    
    return gpa, details

# ============================================================================
# PARSING FUNCTIONS (FLEXIBLE INPUT)
# ============================================================================

def parse_subject_line(line: str) -> Optional[Subject]:
    """
    Parse a single subject line
    Format: [name] [credits] [grade]
    Example: คณิต 3 4
    """
    parts = line.strip().split()
    
    if len(parts) < 3:
        return None
    
    try:
        # Last two parts should be credits and grade
        grade = parts[-1]
        credits = float(parts[-2])
        name = " ".join(parts[:-2])
        
        # Validate
        if not name:
            return None
        if credits <= 0 or credits > 10:
            return None
        if grade not in GRADE_TO_GPA:
            return None
        
        return Subject(name=name, credits=credits, grade=grade)
    
    except (ValueError, IndexError):
        return None

def parse_gpa_input(text: str) -> List[Subject]:
    """
    Parse GPA input - supports multiple formats:
    
    1. Pipe-separated:
       คำนวณ GPA | คณิต 3 4 | ฟิสิกส์ 3 3.5
    
    2. Comma-separated:
       คำนวณ GPA คณิต 3 4, ฟิสิกส์ 3 3.5
    
    3. Space-separated (old format, less reliable):
       คำนวณ GPA คณิต 3 4 ฟิสิกส์ 3 3.5
    """
    # Remove command prefix
    text = text.lower()
    for cmd in ['คำนวณ gpa', 'คำนวณเกรดเฉลี่ย', 'gpa']:
        if text.startswith(cmd):
            text = text[len(cmd):].strip()
            break
    
    subjects = []
    
    # Try pipe-separated first (most reliable)
    if '|' in text:
        parts = text.split('|')
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            subject = parse_subject_line(part)
            if subject:
                subjects.append(subject)
        
        return subjects
    
    # Try comma-separated
    if ',' in text:
        parts = text.split(',')
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            subject = parse_subject_line(part)
            if subject:
                subjects.append(subject)
        
        return subjects
    
    # Try space-separated (least reliable - need to group by 3s)
    parts = text.split()
    
    # Group by 3: [name, credits, grade]
    i = 0
    while i < len(parts):
        # Try to find next valid grade (should be at position i+2)
        if i + 2 < len(parts):
            potential_grade = parts[i + 2]
            
            if potential_grade in GRADE_TO_GPA:
                # Found a valid sequence
                try:
                    name = parts[i]
                    credits = float(parts[i + 1])
                    grade = parts[i + 2]
                    
                    if 0 < credits <= 10:
                        subjects.append(Subject(name=name, credits=credits, grade=grade))
                        i += 3
                        continue
                except (ValueError, IndexError):
                    pass
        
        i += 1
    
    return subjects

# ============================================================================
# MESSAGE FORMATTING
# ============================================================================

def format_gpa_result(gpa: float, details: Dict) -> str:
    """Format GPA calculation result"""
    if "error" in details:
        return details['error']
    
    message = f"GPA ของคุณ\n\n"
    message += f"GPA: {gpa:.2f}\n"
    message += f"จำนวนวิชา: {details['subject_count']} วิชา\n"
    message += f"หน่วยกิตรวม: {details['total_credits']:.1f} หน่วยกิต\n"
    
    # Grade interpretation
    if gpa >= 3.5:
        message += f"\nยอดเยี่ยมมากเลย"
    elif gpa >= 3.0:
        message += f"\nดีมาก พยายามต่อไปนะ"
    elif gpa >= 2.5:
        message += f"\nดี ยังมีที่พัฒนาได้อีก"
    elif gpa >= 2.0:
        message += f"\nพอใช้ได้ ลองตั้งใจเรียนมากขึ้นนะ"
    else:
        message += f"\nเทอมหน้าสู้ใหม่ได้เลย"
    
    if details.get("invalid_subjects"):
        message += f"\n\nวิชาที่ข้อมูลไม่ถูกต้อง:\n"
        for subj in details["invalid_subjects"]:
            message += f"  {subj}\n"
    
    return message

def format_score_to_grade(score: float, grade: str, gpa: float) -> str:
    """Format score to grade result"""
    message = f"คะแนน {score}\n"
    message += f"เกรด: {grade}\n"
    message += f"GPA: {gpa}\n\n"
    
    if gpa >= 3.5:
        message += "เยี่ยมมาก"
    elif gpa >= 3.0:
        message += "ดีมาก"
    elif gpa >= 2.5:
        message += "ดี"
    elif gpa >= 2.0:
        message += "พอใช้ได้"
    else:
        message += "เทอมหน้าสู้ใหม่ได้เลย"
    
    return message

# ============================================================================
# COMMAND HANDLERS
# ============================================================================

def handle_score_to_grade_command(user_message: str) -> str:
    """Handle: คำนวณเกรด 85"""
    try:
        # Extract score
        parts = user_message.split()
        if len(parts) < 2:
            return "บอกคะแนนมาด้วยนะ เช่น คำนวณเกรด 85"
        
        score = float(parts[-1])
        grade = score_to_grade(score)
        gpa = GRADE_TO_GPA[grade]
        
        return format_score_to_grade(score, grade, gpa)
        
    except ValueError:
        return "คะแนนไม่ถูกต้องนะ ต้องเป็นตัวเลข 0-100"
    except Exception as e:
        logger.error(f"Error in score_to_grade: {e}")
        return "คำนวณไม่ได้ ลองใหม่อีกทีนะ"

def handle_gpa_calculation_command(user_message: str, user_id: str = None) -> str:
    """
    Handle GPA calculation - supports multiple formats
    
    Formats supported:
    1. คำนวณ GPA | คณิต 3 4 | ฟิสิกส์ 3 3.5
    2. คำนวณ GPA คณิต 3 4, ฟิสิกส์ 3 3.5
    3. คำนวณ GPA คณิต 3 4 ฟิสิกส์ 3 3.5 (less reliable)
    """
    # Check if this is a session command
    if user_id:
        text_lower = user_message.lower()
        
        # Session commands
        if 'เริ่ม gpa' in text_lower or 'start gpa' in text_lower:
            return start_gpa_session(user_id)
        
        if 'เพิ่มวิชา' in text_lower or 'add subject' in text_lower:
            # Parse: เพิ่มวิชา คณิต 3 4
            text = user_message
            for prefix in ['เพิ่มวิชา', 'add subject']:
                if prefix in text_lower:
                    text = text[text_lower.index(prefix) + len(prefix):].strip()
                    break
            
            subject = parse_subject_line(text)
            
            if not subject:
                return (
                    "รูปแบบไม่ถูกต้องนะ\n"
                    "ใช้: เพิ่มวิชา [ชื่อ] [หน่วยกิต] [เกรด]\n"
                    "เช่น: เพิ่มวิชา คณิต 3 4"
                )
            
            return add_subject_to_session(user_id, subject)
        
        if text_lower in ['คำนวณ gpa', 'calculate gpa', 'คำนวณเกรด']:
            return calculate_session_gpa(user_id)
        
        if 'ยกเลิก gpa' in text_lower or 'cancel gpa' in text_lower:
            return cancel_gpa_session(user_id)
        
        if 'ดู gpa' in text_lower or 'show gpa' in text_lower or 'สถานะ gpa' in text_lower:
            return show_session_status(user_id)
    
    # Try to parse subjects from message
    subjects = parse_gpa_input(user_message)
    
    if not subjects:
        return (
            "วิธีคำนวณ GPA\n\n"
            "แบบทีละวิชา (แนะนำ)\n"
            "1. เริ่ม GPA\n"
            "2. เพิ่มวิชา คณิต 3 4\n"
            "3. เพิ่มวิชา ฟิสิกส์ 3 3.5\n"
            "4. คำนวณ GPA\n\n"
            "แบบใส่ครั้งเดียว (คั่นด้วย |)\n"
            "คำนวณ GPA | คณิต 3 4 | ฟิสิกส์ 3 3.5 | เคมี 2 3\n\n"
            "แบบใส่ครั้งเดียว (คั่นด้วย ,)\n"
            "คำนวณ GPA คณิต 3 4, ฟิสิกส์ 3 3.5, เคมี 2 3\n\n"
            "รูปแบบ: [ชื่อวิชา] [หน่วยกิต] [เกรด]\n"
            "เกรดที่ใช้ได้: 4, 3.5, 3, 2.5, 2, 1.5, 1, 0"
        )
    
    # Calculate GPA
    try:
        gpa, details = calculate_gpa(subjects)
        return format_gpa_result(gpa, details)
    except Exception as e:
        logger.error(f"Error calculating GPA: {e}")
        return f"คำนวณไม่ได้: {str(e)}"

# ============================================================================
# INTEGRATION
# ============================================================================

def get_grade_calculator_commands():
    """Return command tuples for integration"""
    return [
        (("คำนวณเกรด", "เกรดคะแนน"), "score_to_grade"),
        (("คำนวณ gpa", "คำนวณเกรดเฉลี่ย", "gpa"), "gpa_calculation"),
        (("เริ่ม gpa", "start gpa"), "start_gpa_session"),
        (("เพิ่มวิชา", "add subject"), "add_subject"),
        (("ดู gpa", "show gpa", "สถานะ gpa"), "show_gpa_status"),
        (("ยกเลิก gpa", "cancel gpa"), "cancel_gpa_session"),
    ]

def get_grade_calculator_help() -> str:
    """Return help text"""
    return (
        "คำนวณเกรดและ GPA\n\n"
        "วิธีที่ 1 ทีละวิชา (แนะนำ)\n"
        "1. เริ่ม GPA\n"
        "2. เพิ่มวิชา คณิต 3 4\n"
        "3. เพิ่มวิชา ฟิสิกส์ 3 3.5\n"
        "4. คำนวณ GPA\n\n"
        "วิธีที่ 2 ใส่ครั้งเดียว (คั่นด้วย |)\n"
        "คำนวณ GPA | คณิต 3 4 | ฟิสิกส์ 3 3.5 | เคมี 2 3\n\n"
        "วิธีที่ 3 คะแนน → เกรด\n"
        "คำนวณเกรด 85\n\n"
        "รูปแบบ: [ชื่อวิชา] [หน่วยกิต] [เกรด]"
    )

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'handle_score_to_grade_command',
    'handle_gpa_calculation_command',
    'get_grade_calculator_commands',
    'get_grade_calculator_help',
]