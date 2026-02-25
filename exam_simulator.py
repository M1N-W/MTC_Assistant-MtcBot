# -*- coding: utf-8 -*-
"""
MTC Assistant - Exam Simulator Feature (FIXED for google-genai)
ระบบจำลองข้อสอบ ม.ปลาย ด้วย Gemini AI

FIXES:
1. Updated generate_question_with_gemini() to use google-genai client API
2. Fixed API call from gemini_client.models.generate_content() to correct syntax
3. Updated response parsing for google-genai response structure

Features:
- Generate questions using Gemini AI
- 4 subjects: Math, Physics, Chemistry, Biology
- Multiple choice (4 options)
- Answer checking with explanations
- Score tracking in Firebase
- Session management
"""

import json
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from config import logger, LOCAL_TZ
from firebase_admin import firestore as _fs

# ============================================================================
# CONSTANTS
# ============================================================================

SUBJECTS = {
    'math': {
        'name': 'คณิตศาสตร์',
        'emoji': '🧮',
        'topics': ['พีชคณิต', 'แคลคูลัส', 'เรขาคณิต', 'ความน่าจะเป็น', 'สถิติ']
    },
    'physics': {
        'name': 'ฟิสิกส์',
        'emoji': '⚛️',
        'topics': ['กลศาสตร์', 'ไฟฟ้า', 'คลื่น', 'แสง', 'อะตอม']
    },
    'chemistry': {
        'name': 'เคมี',
        'emoji': '🧪',
        'topics': ['อะตอม', 'พันธะเคมี', 'ปฏิกิริยา', 'สารละลาย', 'อินทรีย์']
    },
    'biology': {
        'name': 'ชีววิทยา',
        'emoji': '🧬',
        'topics': ['เซลล์', 'พันธุกรรม', 'วิวัฒนาการ', 'นิเวศ', 'ร่างกาย']
    }
}

DIFFICULTY_LEVELS = {
    'easy': {'name': 'ง่าย', 'emoji': '😊'},
    'medium': {'name': 'กลาง', 'emoji': '🤔'},
    'hard': {'name': 'ยาก', 'emoji': '🔥'}
}

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Question:
    """Single exam question"""
    subject: str
    difficulty: str
    question_text: str
    choices: List[str]  # 4 choices
    correct_answer: int  # 0-3 (index)
    explanation: str

@dataclass
class ExamSession:
    """Active exam session"""
    user_id: str
    subject: str
    difficulty: str
    questions: List[Question]
    current_index: int
    answers: List[int]  # user's answers
    score: int
    started_at: str
    
    def to_dict(self):
        """Convert to dict for storage"""
        return {
            'user_id': self.user_id,
            'subject': self.subject,
            'difficulty': self.difficulty,
            'questions': [asdict(q) for q in self.questions],
            'current_index': self.current_index,
            'answers': self.answers,
            'score': self.score,
            'started_at': self.started_at
        }
    
    @staticmethod
    def from_dict(data: dict):
        """Load from dict"""
        questions = [Question(**q) for q in data['questions']]
        return ExamSession(
            user_id=data['user_id'],
            subject=data['subject'],
            difficulty=data['difficulty'],
            questions=questions,
            current_index=data['current_index'],
            answers=data['answers'],
            score=data['score'],
            started_at=data['started_at']
        )

# ============================================================================
# GEMINI AI INTEGRATION - ✅ FIXED for google-genai
# ============================================================================

def generate_question_with_gemini(
    gemini_client,
    gemini_model: str,
    subject: str,
    difficulty: str
) -> Optional[Question]:
    """
    Generate a single question using Gemini AI
    ✅ FIXED: Updated to use google-genai client API
    
    Args:
        gemini_client: Gemini client instance (google.genai.Client)
        gemini_model: Model name (e.g., 'gemini-3-flash-preview')
        subject: Subject key (math, physics, etc.)
        difficulty: Difficulty level (easy, medium, hard)
    
    Returns:
        Question object or None if failed
    """
    if not gemini_client:
        logger.error("Gemini client not available")
        return None
    
    subject_info = SUBJECTS.get(subject)
    if not subject_info:
        logger.error(f"Invalid subject: {subject}")
        return None
    
    difficulty_name = DIFFICULTY_LEVELS.get(difficulty, {}).get('name', 'กลาง')
    
    # Create prompt for Gemini
    prompt = f"""สร้างข้อสอบ {subject_info['name']} ระดับมัธยมปลาย ความยาก: {difficulty_name}

กรุณาสร้างคำถามพร้อม:
1. คำถาม (ชัดเจน เข้าใจง่าย)
2. 4 ตัวเลือก (A, B, C, D)
3. คำตอบที่ถูกต้อง (ระบุเลข 0-3)
4. คำอธิบายเฉลย

โปรดตอบในรูปแบบ JSON เท่านั้น:
{{
    "question": "คำถาม",
    "choices": ["ตัวเลือก A", "ตัวเลือก B", "ตัวเลือก C", "ตัวเลือก D"],
    "correct_answer": 0,
    "explanation": "คำอธิบาย"
}}

หมายเหตุ: อย่าใส่ ```json หรือ markdown อื่นๆ ตอบแค่ JSON ล้วนๆ"""
    
    try:
        # ✅ FIXED: Use google-genai API
        response = gemini_client.models.generate_content(
            model=gemini_model,
            contents=prompt
        )
        
        # Parse response - ✅ FIXED: Handle google-genai response structure
        response_text = ""
        
        # Try to get text from response
        if hasattr(response, "text") and response.text:
            response_text = str(response.text).strip()
        elif hasattr(response, "candidates") and response.candidates:
            # Handle candidates structure
            first_candidate = response.candidates[0]
            if hasattr(first_candidate, "content") and first_candidate.content:
                content = first_candidate.content
                if hasattr(content, "parts") and content.parts:
                    parts_text = []
                    for part in content.parts:
                        if hasattr(part, "text") and part.text:
                            parts_text.append(str(part.text))
                    if parts_text:
                        response_text = "".join(parts_text).strip()
        
        if not response_text:
            logger.error("Empty response from Gemini")
            return None
        
        # Clean response (remove markdown if present)
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Parse JSON
        data = json.loads(response_text)
        
        # Validate data
        if not all(key in data for key in ['question', 'choices', 'correct_answer', 'explanation']):
            logger.error("Missing required fields in response")
            return None
        
        if len(data['choices']) != 4:
            logger.error(f"Expected 4 choices, got {len(data['choices'])}")
            return None
        
        if not (0 <= data['correct_answer'] <= 3):
            logger.error(f"Invalid correct_answer: {data['correct_answer']}")
            return None
        
        # Create Question object
        question = Question(
            subject=subject,
            difficulty=difficulty,
            question_text=data['question'],
            choices=data['choices'],
            correct_answer=int(data['correct_answer']),
            explanation=data['explanation']
        )
        
        logger.info(f"Generated question for {subject} ({difficulty})")
        return question
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        logger.error(f"Response was: {response_text[:200]}")
        return None
    except Exception as e:
        logger.error(f"Error generating question: {e}")
        return None

# ============================================================================
# SESSION MANAGER
# ============================================================================

class ExamSessionManager:
    """Manage active exam sessions"""
    
    def __init__(self, db=None):
        """Initialize session manager"""
        self.db = db
        self.active_sessions: Dict[str, ExamSession] = {}
    
    def create_session(
        self,
        user_id: str,
        subject: str,
        difficulty: str,
        num_questions: int,
        gemini_client,
        gemini_model: str
    ) -> Tuple[bool, str]:
        """
        Create new exam session
        
        Returns:
            (success, message)
        """
        # Check if user already has active session
        if user_id in self.active_sessions:
            return False, "❌ คุณมีข้อสอบที่ยังทำไม่เสร็จ\nพิมพ์ 'ยกเลิกสอบ' เพื่อยกเลิก"
        
        # Validate inputs
        if subject not in SUBJECTS:
            return False, f"❌ วิชาไม่ถูกต้อง: {subject}"
        
        if difficulty not in DIFFICULTY_LEVELS:
            return False, f"❌ ระดับความยากไม่ถูกต้อง: {difficulty}"
        
        if not (1 <= num_questions <= 10):
            return False, "❌ จำนวนข้อต้องอยู่ระหว่าง 1-10 ข้อ"
        
        # Generate questions
        questions = []
        for i in range(num_questions):
            logger.info(f"Generating question {i+1}/{num_questions}...")
            question = generate_question_with_gemini(
                gemini_client,
                gemini_model,
                subject,
                difficulty
            )
            
            if question:
                questions.append(question)
            else:
                logger.warning(f"Failed to generate question {i+1}")
        
        if not questions:
            return False, "❌ ไม่สามารถสร้างข้อสอบได้ กรุณาลองใหม่อีกครั้ง"
        
        # Create session
        session = ExamSession(
            user_id=user_id,
            subject=subject,
            difficulty=difficulty,
            questions=questions,
            current_index=0,
            answers=[],
            score=0,
            started_at=datetime.now(tz=LOCAL_TZ).isoformat()
        )
        
        self.active_sessions[user_id] = session
        
        subject_name = SUBJECTS[subject]['name']
        difficulty_name = DIFFICULTY_LEVELS[difficulty]['name']
        
        return True, (
            f"✅ สร้างข้อสอบสำเร็จ!\n\n"
            f"📚 วิชา: {subject_name}\n"
            f"📊 ระดับ: {difficulty_name}\n"
            f"📝 จำนวน: {len(questions)} ข้อ\n\n"
            f"กรุณารอสักครู่... กำลังส่งข้อแรก"
        )
    
    def get_session(self, user_id: str) -> Optional[ExamSession]:
        """Get active session for user"""
        return self.active_sessions.get(user_id)
    
    def has_active_session(self, user_id: str) -> bool:
        """Check if user has active session"""
        return user_id in self.active_sessions
    
    def submit_answer(self, user_id: str, answer: int) -> Tuple[bool, str]:
        """
        Submit answer for current question
        
        Args:
            user_id: User ID
            answer: Answer index (0-3 or 1-4)
        
        Returns:
            (success, message)
        """
        session = self.get_session(user_id)
        if not session:
            return False, "❌ ไม่พบข้อสอบที่กำลังทำอยู่"
        
        # Convert 1-4 to 0-3
        if 1 <= answer <= 4:
            answer = answer - 1
        
        if not (0 <= answer <= 3):
            return False, "❌ คำตอบต้องเป็น 1, 2, 3, หรือ 4"
        
        # Get current question
        current_q = session.questions[session.current_index]
        
        # Save answer
        session.answers.append(answer)
        
        # Check if correct
        is_correct = (answer == current_q.correct_answer)
        if is_correct:
            session.score += 1
        
        # Move to next question
        session.current_index += 1
        
        # Build per-answer feedback
        if is_correct:
            feedback = "✅ ถูกต้อง!"
        else:
            feedback = f"❌ ผิด! คำตอบที่ถูกต้องคือข้อ {current_q.correct_answer + 1}"

        # Check if exam is complete
        if session.current_index >= len(session.questions):
            return True, self._finish_exam(user_id)

        return True, feedback
    
    def _finish_exam(self, user_id: str) -> str:
        """Finish exam and show results"""
        session = self.get_session(user_id)
        if not session:
            return "❌ เกิดข้อผิดพลาด"
        
        # Calculate score
        total = len(session.questions)
        score = session.score
        percentage = (score / total) * 100
        
        # Determine grade
        if percentage >= 80:
            grade = "A (ดีเยี่ยม 🌟)"
        elif percentage >= 70:
            grade = "B (ดี 😊)"
        elif percentage >= 60:
            grade = "C (ปานกลาง 👍)"
        elif percentage >= 50:
            grade = "D (พอใช้ 💪)"
        else:
            grade = "F (ควรปรับปรุง 📚)"
        
        # Save to database
        if self.db:
            try:
                self.db.collection('exam_results').add({
                    'user_id': user_id,
                    'subject': session.subject,
                    'difficulty': session.difficulty,
                    'score': score,
                    'total': total,
                    'percentage': percentage,
                    'started_at': session.started_at,
                    'completed_at': datetime.now(tz=LOCAL_TZ).isoformat()
                })
                logger.info(f"Saved exam result for {user_id}: {score}/{total}")
            except Exception as e:
                logger.error(f"Failed to save exam result: {e}")
        
        # Build result message
        subject_name = SUBJECTS[session.subject]['name']
        difficulty_name = DIFFICULTY_LEVELS[session.difficulty]['name']
        
        result_msg = (
            f"🎓 *ผลการสอบ*\n\n"
            f"📚 วิชา: {subject_name}\n"
            f"📊 ระดับ: {difficulty_name}\n"
            f"✅ คะแนน: {score}/{total} ({percentage:.1f}%)\n"
            f"🏆 เกรด: {grade}\n\n"
        )
        
        # Add review
        if percentage >= 80:
            result_msg += "💯 เก่งมาก! คุณเข้าใจเนื้อหาได้ดีแล้ว\n"
        elif percentage >= 60:
            result_msg += "👍 ดีมาก! ยังมีที่ปรับปรุงนิดหน่อย\n"
        else:
            result_msg += "📚 ลองทบทวนเนื้อหาอีกครั้งนะ\n"
        
        result_msg += "\n💡 พิมพ์ 'เฉลยข้อสอบ' เพื่อดูเฉลยทุกข้อ"
        
        return result_msg
    
    def get_explanation(self, user_id: str) -> str:
        """Get explanation for all questions"""
        session = self.get_session(user_id)
        if not session:
            return "❌ ไม่พบข้อสอบที่เสร็จแล้ว"
        
        if session.current_index < len(session.questions):
            return "❌ กรุณาทำข้อสอบให้เสร็จก่อน"
        
        msg = f"📝 *เฉลยข้อสอบ*\n\n"
        
        for i, question in enumerate(session.questions, 1):
            user_answer = session.answers[i-1] if i-1 < len(session.answers) else -1
            is_correct = (user_answer == question.correct_answer)
            
            msg += f"*ข้อ {i}:* {question.question_text}\n\n"
            
            for j, choice in enumerate(question.choices):
                marker = ""
                if j == question.correct_answer:
                    marker = "✅ "
                elif j == user_answer and not is_correct:
                    marker = "❌ "
                
                msg += f"{marker}{j+1}. {choice}\n"
            
            msg += f"\n💡 *คำอธิบาย:* {question.explanation}\n"
            msg += "─" * 30 + "\n\n"
        
        # Clean up session
        del self.active_sessions[user_id]
        
        return msg
    
    def cancel_session(self, user_id: str) -> str:
        """Cancel active session"""
        if user_id in self.active_sessions:
            del self.active_sessions[user_id]
            return "✅ ยกเลิกข้อสอบเรียบร้อยแล้ว"
        return "❌ ไม่พบข้อสอบที่กำลังทำอยู่"
    
    def get_current_question(self, user_id: str) -> str:
        """Get current question as formatted message"""
        session = self.get_session(user_id)
        if not session:
            return "❌ ไม่พบข้อสอบที่กำลังทำอยู่"
        
        if session.current_index >= len(session.questions):
            return "✅ คุณทำข้อสอบเสร็จแล้ว!"
        
        question = session.questions[session.current_index]
        question_num = session.current_index + 1
        total = len(session.questions)
        
        msg = f"❓ *ข้อที่ {question_num}/{total}*\n\n"
        msg += f"{question.question_text}\n\n"
        
        for i, choice in enumerate(question.choices, 1):
            msg += f"{i}. {choice}\n"
        
        msg += f"\n💬 ตอบเลข 1-4\n"
        msg += f"📊 ทำไปแล้ว: {session.current_index}/{total} ข้อ"
        
        return msg

# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

_session_manager: Optional[ExamSessionManager] = None

def get_session_manager(db=None) -> ExamSessionManager:
    """Get or create global session manager"""
    global _session_manager
    if _session_manager is None:
        _session_manager = ExamSessionManager(db)
    elif db is not None and _session_manager.db is None:
        _session_manager.db = db
    return _session_manager

# ============================================================================
# COMMAND HANDLERS
# ============================================================================

def handle_start_exam_command(
    user_id: str,
    user_message: str,
    gemini_client,
    gemini_model: str,
    db=None
) -> str:
    """
    Handle start exam command
    
    Format: สอบ [วิชา] [ระดับ] [จำนวนข้อ]
    Examples:
        - สอบ คณิต ง่าย 5
        - สอบ ฟิสิกส์ กลาง 3
        - สอบ เคมี ยาก 10
    """
    manager = get_session_manager(db)
    
    # Parse command
    parts = user_message.lower().split()
    
    if len(parts) < 2:
        return (
            "📚 *ข้อสอบจำลอง*\n\n"
            "💡 วิธีใช้:\n"
            "สอบ [วิชา] [ระดับ] [จำนวนข้อ]\n\n"
            "📖 *วิชาที่มี:*\n"
            "• คณิต (คณิตศาสตร์)\n"
            "• ฟิสิกส์\n"
            "• เคมี\n"
            "• ชีวะ (ชีววิทยา)\n\n"
            "📊 *ระดับความยาก:*\n"
            "• ง่าย\n"
            "• กลาง\n"
            "• ยาก\n\n"
            "📝 *ตัวอย่าง:*\n"
            "สอบ คณิต ง่าย 5\n"
            "สอบ ฟิสิกส์ กลาง 3"
        )
    
    # Map Thai subject names
    subject_map = {
        'คณิต': 'math',
        'คณิตศาสตร์': 'math',
        'ฟิสิกส์': 'physics',
        'ฟิสิก': 'physics',
        'เคมี': 'chemistry',
        'ชีวะ': 'biology',
        'ชีววิทยา': 'biology'
    }
    
    difficulty_map = {
        'ง่าย': 'easy',
        'กลาง': 'medium',
        'ยาก': 'hard'
    }
    
    # Parse subject
    subject_thai = parts[1]
    subject = subject_map.get(subject_thai)
    
    if not subject:
        return f"❌ วิชาไม่ถูกต้อง: {subject_thai}\nวิชาที่มี: คณิต, ฟิสิกส์, เคมี, ชีวะ"
    
    # Parse difficulty (default: medium)
    difficulty = 'medium'
    num_questions = 5
    
    if len(parts) >= 3:
        difficulty_thai = parts[2]
        difficulty = difficulty_map.get(difficulty_thai, 'medium')
    
    # Parse number of questions
    if len(parts) >= 4:
        try:
            num_questions = int(parts[3])
        except ValueError:
            return "❌ จำนวนข้อต้องเป็นตัวเลข"
    
    # Create session
    success, message = manager.create_session(
        user_id,
        subject,
        difficulty,
        num_questions,
        gemini_client,
        gemini_model
    )
    
    return message

def handle_answer_command(
    user_id: str,
    user_message: str,
    db=None
) -> Tuple[str, bool]:
    """
    Handle answer submission
    
    Returns:
        (message, send_next_question)
    """
    manager = get_session_manager(db)
    
    # Check if user has active session
    if not manager.has_active_session(user_id):
        return "", False
    
    # Try to parse answer
    try:
        text = user_message.strip().lower()
        
        # Remove common prefixes
        for prefix in ['ตอบ', 'คือ', 'เลือก', 'ข้อ']:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        
        # Try to extract number
        answer = int(text)
        
        # Submit answer
        success, message = manager.submit_answer(user_id, answer)
        
        if not success:
            return message, False
        
        if message:  # Exam finished
            return message, False
        else:  # Continue to next question
            return "", True
        
    except ValueError:
        return "❌ กรุณาตอบเป็นตัวเลข 1-4", False

def handle_show_current_question(user_id: str, db=None) -> str:
    """Show current question"""
    manager = get_session_manager(db)
    return manager.get_current_question(user_id)

def handle_cancel_exam(user_id: str, db=None) -> str:
    """Cancel active exam"""
    manager = get_session_manager(db)
    return manager.cancel_session(user_id)

def handle_show_explanation(user_id: str, db=None) -> str:
    """Show explanation for completed exam"""
    manager = get_session_manager(db)
    return manager.get_explanation(user_id)

def handle_exam_stats(user_id: str, db=None) -> str:
    """Show user's exam statistics"""
    if not db:
        return "⚠️ ระบบฐานข้อมูลยังไม่พร้อม"
    
    try:
        # Get user's exam results
        results = db.collection('exam_results')\
            .where('user_id', '==', user_id)\
            .order_by('completed_at', direction=_fs.Query.DESCENDING)\
            .limit(10)\
            .stream()
        
        result_list = []
        total_score = 0
        total_count = 0
        
        for doc in results:
            data = doc.to_dict()
            result_list.append(data)
            total_score += data.get('percentage', 0)
            total_count += 1
        
        if total_count == 0:
            return "📊 *สถิติการสอบ*\n\nยังไม่มีประวัติการทำข้อสอบ"
        
        avg_score = total_score / total_count
        
        msg = f"📊 *สถิติการสอบของคุณ*\n\n"
        msg += f"📈 ค่าเฉลี่ย: {avg_score:.1f}%\n"
        msg += f"📝 ทำไปแล้ว: {total_count} ครั้ง\n\n"
        msg += f"*ประวัติล่าสุด:*\n\n"
        
        for i, result in enumerate(result_list[:5], 1):
            subject_name = SUBJECTS.get(result['subject'], {}).get('name', 'ไม่ระบุ')
            difficulty_name = DIFFICULTY_LEVELS.get(result['difficulty'], {}).get('name', 'กลาง')
            
            msg += f"{i}. {subject_name} ({difficulty_name})\n"
            msg += f"   {result['score']}/{result['total']} ({result['percentage']:.0f}%)\n\n"
        
        return msg
        
    except Exception as e:
        logger.error(f"Error getting exam stats: {e}")
        return "❌ เกิดข้อผิดพลาดในการดึงข้อมูล"

# ============================================================================
# INTEGRATION HELPER
# ============================================================================

def get_exam_commands():
    """Return command tuples for integration with handlers.py"""
    return [
        (("สอบจำลอง", "ข้อสอบ", "สอบ"), "start_exam"),
        (("ยกเลิกสอบ", "cancel exam"), "cancel_exam"),
        (("เฉลยข้อสอบ", "ดูเฉลย"), "show_explanation"),
        (("สถิติสอบ", "exam stats", "ประวัติสอบ"), "exam_stats"),
    ]

def get_exam_help() -> str:
    """Return help text for exam simulator"""
    return """
📚 *ข้อสอบจำลอง ม.ปลาย*

• สอบ [วิชา] [ระดับ] [จำนวนข้อ]
  ตัวอย่าง: สอบ คณิต ง่าย 5

• [เลข 1-4] = ตอบคำถาม

• เฉลยข้อสอบ = ดูเฉลยทั้งหมด

• สถิติสอบ = ดูประวัติการสอบ

• ยกเลิกสอบ = ยกเลิกข้อสอบปัจจุบัน

📖 วิชา: คณิต, ฟิสิกส์, เคมี, ชีวะ
📊 ระดับ: ง่าย, กลาง, ยาก
"""

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'ExamSessionManager',
    'get_session_manager',
    'handle_start_exam_command',
    'handle_answer_command',
    'handle_show_current_question',
    'handle_cancel_exam',
    'handle_show_explanation',
    'handle_exam_stats',
    'get_exam_commands',
    'get_exam_help',
]
