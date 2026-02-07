# -*- coding: utf-8 -*-
"""
MTC Assistant - Grade Calculator Feature
คำนวณเกรดและ GPA
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class Subject:
    """Subject with grade and credits"""
    name: str
    credits: float
    grade: str
    score: Optional[float] = None

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

SCORE_TO_GRADE = {
    (80, 100): "4",
    (75, 79): "3.5",
    (70, 74): "3",
    (65, 69): "2.5",
    (60, 64): "2",
    (55, 59): "1.5",
    (50, 54): "1",
    (0, 49): "0",
}

def score_to_grade(score: float) -> str:
    """Convert score to grade"""
    if not (0 <= score <= 100):
        raise ValueError("คะแนนต้องอยู่ระหว่าง 0-100")
    for (min_score, max_score), grade in SCORE_TO_GRADE.items():
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
        return 0.0, {"error": "ไม่มีหน่วยกิตที่ถูกต้อง", "invalid_subjects": invalid_subjects}
    gpa = total_grade_points / total_credits
    details = {
        "gpa": round(gpa, 2),
        "total_credits": total_credits,
        "total_grade_points": total_grade_points,
        "subject_count": len(subjects),
        "invalid_subjects": invalid_subjects
    }
    return gpa, details

def format_gpa_result(gpa: float, details: Dict) -> str:
    """Format GPA calculation result for display"""
    if "error" in details:
        return f"❌ {details['error']}"
    message = f"📊 *ผลการคำนวณ GPA*\n\n"
    message += f"🎯 GPA: *{gpa:.2f}*\n"
    message += f"📚 จำนวนวิชา: {details['subject_count']} วิชา\n"
    message += f"💯 หน่วยกิตรวม: {details['total_credits']:.1f} หน่วยกิต\n"
    if gpa >= 3.5:
        message += f"\n🌟 ยอดเยี่ยม! เก่งมาก!"
    elif gpa >= 3.0:
        message += f"\n😊 ดีมาก! พยายามต่อไป"
    elif gpa >= 2.5:
        message += f"\n👍 ดี แต่ยังพอมีที่พัฒนา"
    elif gpa >= 2.0:
        message += f"\n💪 พอใช้ ลองตั้งใจเรียนมากขึ้น"
    else:
        message += f"\n😢 ควรปรับปรุง พยายามนะ!"
    if details.get("invalid_subjects"):
        message += f"\n\n⚠️ วิชาที่ไม่ถูกต้อง:\n"
        for subj in details["invalid_subjects"]:
            message += f"  • {subj}\n"
    return message

def handle_score_to_grade_command(user_message: str) -> str:
    """Handle: คำนวณเกรด 85"""
    try:
        parts = user_message.split()
        if len(parts) < 2:
            return "⚠️ กรุณาระบุคะแนน\nตัวอย่าง: คำนวณเกรด 85"
        score = float(parts[-1])
        grade = score_to_grade(score)
        gpa = GRADE_TO_GPA[grade]
        message = f"📝 *คำนวณเกรดจากคะแนน*\n\n"
        message += f"คะแนน: {score}\n"
        message += f"เกรด: *{grade}*\n"
        message += f"GPA: *{gpa}*\n\n"
        if gpa >= 3.5:
            message += "🌟 เยี่ยมมาก!"
        elif gpa >= 3.0:
            message += "😊 ดีมาก!"
        elif gpa >= 2.5:
            message += "👍 ดี"
        elif gpa >= 2.0:
            message += "💪 พอใช้"
        else:
            message += "😢 ควรปรับปรุง"
        return message
    except ValueError:
        return "❌ คะแนนไม่ถูกต้อง ต้องเป็นตัวเลข 0-100"
    except Exception as e:
        logger.error(f"Error in score_to_grade: {e}")
        return "❌ เกิดข้อผิดพลาดในการคำนวณ"

def handle_gpa_calculation_command(user_message: str) -> str:
    """Handle: คำนวณ GPA วิชา1 3 4 วิชา2 2 3.5"""
    try:
        parts = user_message.replace("คำนวณ", "").replace("gpa", "", 1).replace("เกรดเฉลี่ย", "").strip().split()
        if len(parts) < 3:
            return (
                "⚠️ รูปแบบคำสั่ง:\n"
                "คำนวณ GPA [วิชา] [หน่วยกิต] [เกรด] ...\n\n"
                "ตัวอย่าง:\n"
                "คำนวณ GPA คณิต 3 4 ฟิสิกส์ 3 3.5 เคมี 2 3"
            )
        subjects = []
        i = 0
        while i < len(parts) - 2:
            try:
                name = parts[i]
                credits = float(parts[i + 1])
                grade = parts[i + 2]
                subjects.append(Subject(name, credits, grade))
                i += 3
            except (ValueError, IndexError):
                i += 1
        if not subjects:
            return "❌ ไม่พบข้อมูลวิชาที่ถูกต้อง"
        gpa, details = calculate_gpa(subjects)
        return format_gpa_result(gpa, details)
    except Exception as e:
        logger.error(f"Error in GPA calculation: {e}")
        return "❌ เกิดข้อผิดพลาดในการคำนวณ GPA"

__all__ = [
    'Subject',
    'GRADE_TO_GPA',
    'SCORE_TO_GRADE',
    'score_to_grade',
    'calculate_gpa',
    'format_gpa_result',
    'handle_score_to_grade_command',
    'handle_gpa_calculation_command',
]
