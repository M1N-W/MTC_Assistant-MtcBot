# 🚀 MTC Assistant - Feature Expansion Roadmap

> **Legacy and non-authoritative:** This is an old feature-idea backlog. It
> must not define current implementation order. Current roadmap authority is
> [MTC OS Master Plan](mtc-os-master-plan.md). Architecture examples below may
> no longer match the repository. Historical content is preserved.

**Project:** MTC Assistant v21  
**Current Features:** 20+  
**Code Quality:** 9/10  
**Date:** April 26, 2026 (อัปเดตล่าสุด)  

---

## 📊 **Current System Overview**

### **Existing Architecture:**
```
Language: Python 3.8+
Framework: Flask 2.0+
LINE SDK: 3.0+
AI: Google Gemini 3.0
Database: Firebase Firestore
Deployment: Render
```

### **Project Structure:**
```
mtc-assistant/
├── main.py          # Flask app & initialization
├── config.py        # Configuration & constants
├── features.py      # Feature implementations
├── handlers.py      # LINE event handlers
├── broadcast.py     # Broadcast system
└── firebase_key.json
```

### **Current Features (20+):**
```
Academic (10):
  1. Schedule Management (ตารางเรียน real-time)
  2. Class Time Tracking (คาบต่อไป + เวลาที่เหลือ)
  3. Homework Session (เพิ่ม/ดู/ลบแบบ interactive)
  4. Exam Countdown (กลางภาค/ปลายภาค multi-date)
  5. Exam Simulator (สุ่มข้อสอบ + เฉลยด้วย Gemini)
  6. Grade & GPA Calculator (session-based + multi-format)
  7. Smart Calc (AST evaluator + per-user variables)
  8. Links Repository (Flex Message)
  9. Music Search (YouTube API)
  10. AI Chat (Gemini Dual-model + Fallback)

Admin (5):
  11. Broadcast System (rate-limited + retry)
  12. Admin Impersonate (push message + exponential backoff)
  13. User Blacklist (Firestore + in-memory cache)
  14. User Tracking & Stats (O(1) counter)
  15. Help & Identity Module

Infrastructure (5+):
  16. Rate Limiting (per-user sliding window)
  17. Error Handling (graceful + persona-aware messages)
  18. Connection Pooling (gthread worker)
  19. Metrics Tracking (request/error/latency)
  20. Firebase via ENV (FIREBASE_CREDENTIALS_JSON / _BASE64)
  21. Health check (/healthz JSON + non-blocking probe)
```

---

## 💡 **New Feature Opportunities (25+ Ideas)**

### **Tier 1: High Impact, Medium Complexity** ⭐⭐⭐⭐⭐

#### **1. Grade Calculator & GPA Tracker** 🎓 ✅ เสร็จแล้ว
```
Value Proposition: คำนวณเกรดและ GPA อัตโนมัติ
Impact: Very High (ใช้บ่อย)
Complexity: Medium
Time: 2-3 hours
Status: ✅ DONE — เห็นได้ที่ grade_calculator.py
```

**Features:**
- Score to grade conversion (คะแนน → เกรด)
- GPA calculation (หลายวิชา)
- Target GPA prediction (ต้องได้เกรดเท่าไหร่)
- Semester tracking

**Commands:**
```
• คำนวณเกรด 85
  → เกรด: 4, GPA: 4.0

• คำนวณ GPA คณิต 3 4 ฟิสิกส์ 3 3.5
  → GPA: 3.75

• เกรดเป้าหมาย 3.5
  → ต้องได้เกรด 3.5+ ในวิชาถัดไป
```

**Implementation:** ✅ Already created (grade_calculator.py)

**Integration:**
```python
# In handlers.py
from grade_calculator import get_grade_calculator_commands

COMMANDS += get_grade_calculator_commands()
```

**Testing:**
```bash
# Test commands
"คำนวณเกรด 85"
"คำนวณ GPA คณิต 3 4 ฟิสิกส์ 3 3.5"
```

---

#### **2. Quick Notes System** 📝
```
Value Proposition: บันทึกโน้ตด่วนๆ ได้ทุกที่
Impact: High
Complexity: Medium
Time: 2-3 hours
```

**Features:**
- Create notes (text, voice-to-text)
- List all notes
- Search notes
- Delete notes
- Tag system (#math, #physics)

**Commands:**
```
• บันทึก [ข้อความ]
  → บันทึก สูตร f=ma #physics

• ดูโน้ต
  → แสดงโน้ตทั้งหมด

• ค้นหาโน้ต [keyword]
  → ค้นหาโน้ต physics

• ลบโน้ต [id]
  → ลบโน้ต note_123
```

**Design:**

```python
# quick_notes.py
from firebase_admin import firestore
import datetime

class QuickNotes:
    def __init__(self, db):
        self.db = db
        self.collection = 'quick_notes'
    
    def create_note(self, user_id: str, content: str, tags: list = None):
        """Create a new note"""
        note_ref = self.db.collection(self.collection).document()
        
        note_data = {
            'user_id': user_id,
            'content': content,
            'tags': tags or [],
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        
        note_ref.set(note_data)
        return note_ref.id
    
    def get_user_notes(self, user_id: str, limit: int = 10):
        """Get all notes for a user"""
        notes = self.db.collection(self.collection)\
            .where('user_id', '==', user_id)\
            .order_by('created_at', direction=firestore.Query.DESCENDING)\
            .limit(limit)\
            .stream()
        
        return [
            {
                'id': note.id,
                **note.to_dict()
            }
            for note in notes
        ]
    
    def search_notes(self, user_id: str, keyword: str):
        """Search notes by keyword"""
        all_notes = self.get_user_notes(user_id, limit=50)
        
        keyword_lower = keyword.lower()
        return [
            note for note in all_notes
            if keyword_lower in note['content'].lower()
        ]
    
    def delete_note(self, note_id: str, user_id: str):
        """Delete a note (with ownership check)"""
        note_ref = self.db.collection(self.collection).document(note_id)
        note = note_ref.get()
        
        if not note.exists:
            return False, "โน้ตไม่พบ"
        
        if note.to_dict().get('user_id') != user_id:
            return False, "คุณไม่มีสิทธิ์ลบโน้ตนี้"
        
        note_ref.delete()
        return True, "ลบโน้ตสำเร็จ"

def format_notes_list(notes: list) -> str:
    """Format notes for display"""
    if not notes:
        return "📝 ยังไม่มีโน้ต"
    
    message = f"📝 *โน้ตของคุณ* ({len(notes)} รายการ)\n\n"
    
    for i, note in enumerate(notes[:10], 1):
        content = note['content'][:50] + "..." if len(note['content']) > 50 else note['content']
        
        tags = ""
        if note.get('tags'):
            tags = " " + " ".join(f"#{tag}" for tag in note['tags'])
        
        message += f"{i}. {content}{tags}\n"
        message += f"   (ID: {note['id'][-6:]})\n\n"
    
    if len(notes) > 10:
        message += f"... และอีก {len(notes) - 10} โน้ต"
    
    return message

# Command handlers
def handle_create_note(user_id: str, user_message: str, notes_service: QuickNotes) -> str:
    """Handle: บันทึก [content]"""
    content = user_message.replace("บันทึก", "").strip()
    
    if not content:
        return "⚠️ กรุณาระบุเนื้อหาโน้ต\nตัวอย่าง: บันทึก สูตร f=ma"
    
    # Extract tags
    tags = [word[1:] for word in content.split() if word.startswith("#")]
    
    try:
        note_id = notes_service.create_note(user_id, content, tags)
        return f"✅ บันทึกโน้ตสำเร็จ!\n(ID: {note_id[-6:]})"
    except Exception as e:
        return f"❌ เกิดข้อผิดพลาด: {str(e)}"

def handle_list_notes(user_id: str, notes_service: QuickNotes) -> str:
    """Handle: ดูโน้ต"""
    try:
        notes = notes_service.get_user_notes(user_id)
        return format_notes_list(notes)
    except Exception as e:
        return f"❌ เกิดข้อผิดพลาด: {str(e)}"

def handle_search_notes(user_id: str, user_message: str, notes_service: QuickNotes) -> str:
    """Handle: ค้นหาโน้ต [keyword]"""
    keyword = user_message.replace("ค้นหาโน้ต", "").strip()
    
    if not keyword:
        return "⚠️ กรุณาระบุคำค้นหา\nตัวอย่าง: ค้นหาโน้ต physics"
    
    try:
        notes = notes_service.search_notes(user_id, keyword)
        return format_notes_list(notes)
    except Exception as e:
        return f"❌ เกิดข้อผิดพลาด: {str(e)}"
```

**File Changes:**
```
New Files:
  + quick_notes.py

Modified Files:
  ~ handlers.py (add commands)
  ~ main.py (initialize QuickNotes service)
```

**Testing Steps:**
```
1. บันทึก ทดสอบโน้ต #test
   → ✅ บันทึกสำเร็จ

2. ดูโน้ต
   → แสดงโน้ตทั้งหมด

3. ค้นหาโน้ต test
   → แสดงโน้ตที่มี "test"

4. ลบโน้ต [id]
   → ลบสำเร็จ
```

---

#### **3. Expense Tracker (ติดตามค่าใช้จ่าย)** 💰
```
Value Proposition: จดบัญชีรายรับรายจ่าย
Impact: High (เด็กนักเรียนต้องการ!)
Complexity: Medium
Time: 3-4 hours
```

**Features:**
- Add expense/income
- View summary (daily/weekly/monthly)
- Category tracking
- Budget alerts
- Export to Excel

**Commands:**
```
• จ่าย 50 ข้าว
  → บันทึกค่าใช้จ่าย 50 บาท

• รับ 500 เงินเดือน
  → บันทึกรายรับ 500 บาท

• ดูยอด
  → สรุปรายรับรายจ่าย

• สรุปเดือนนี้
  → รายงานประจำเดือน
```

**Design:**
```python
# expense_tracker.py
from enum import Enum
from dataclasses import dataclass
import datetime

class TransactionType(Enum):
    INCOME = "income"
    EXPENSE = "expense"

@dataclass
class Transaction:
    user_id: str
    amount: float
    type: TransactionType
    category: str
    description: str
    date: datetime.date

class ExpenseTracker:
    CATEGORIES = {
        'income': ['เงินเดือน', 'เงินพ่อแม่', 'ขายของ', 'อื่นๆ'],
        'expense': ['อาหาร', 'เครื่องเขียน', 'ค่ารถ', 'ของเล่น', 'อื่นๆ']
    }
    
    def __init__(self, db):
        self.db = db
        self.collection = 'transactions'
    
    def add_transaction(
        self,
        user_id: str,
        amount: float,
        trans_type: TransactionType,
        description: str,
        category: str = "อื่นๆ"
    ):
        """Add income or expense"""
        trans_ref = self.db.collection(self.collection).document()
        
        trans_data = {
            'user_id': user_id,
            'amount': amount,
            'type': trans_type.value,
            'category': category,
            'description': description,
            'date': datetime.datetime.now(),
            'created_at': firestore.SERVER_TIMESTAMP
        }
        
        trans_ref.set(trans_data)
        return trans_ref.id
    
    def get_balance(self, user_id: str, start_date=None, end_date=None):
        """Calculate balance"""
        query = self.db.collection(self.collection).where('user_id', '==', user_id)
        
        if start_date:
            query = query.where('date', '>=', start_date)
        if end_date:
            query = query.where('date', '<=', end_date)
        
        transactions = query.stream()
        
        income = 0
        expense = 0
        
        for trans in transactions:
            data = trans.to_dict()
            if data['type'] == 'income':
                income += data['amount']
            else:
                expense += data['amount']
        
        return {
            'income': income,
            'expense': expense,
            'balance': income - expense,
            'transactions_count': income + expense
        }
    
    def get_monthly_summary(self, user_id: str, year: int, month: int):
        """Get summary for specific month"""
        start_date = datetime.date(year, month, 1)
        
        if month == 12:
            end_date = datetime.date(year + 1, 1, 1)
        else:
            end_date = datetime.date(year, month + 1, 1)
        
        return self.get_balance(user_id, start_date, end_date)

def format_balance(balance_data: dict) -> str:
    """Format balance for display"""
    message = "💰 *สรุปรายรับรายจ่าย*\n\n"
    message += f"📈 รายรับ: +{balance_data['income']:.2f} บาท\n"
    message += f"📉 รายจ่าย: -{balance_data['expense']:.2f} บาท\n"
    message += f"{'─' * 25}\n"
    
    balance = balance_data['balance']
    if balance >= 0:
        message += f"💵 คงเหลือ: {balance:.2f} บาท ✅\n"
    else:
        message += f"⚠️ ขาดดุล: {abs(balance):.2f} บาท\n"
    
    return message
```

---

### **Tier 2: Medium Impact, Low Complexity** ⭐⭐⭐⭐

#### **4. Study Timer (Pomodoro)** ⏱️
```
Impact: Medium-High
Complexity: Low
Time: 1-2 hours
```

**Features:**
- Start/stop timer
- Pomodoro technique (25 min work, 5 min break)
- Study statistics
- Focus mode reminders

**Commands:**
```
• ตั้งเวลาอ่านหนังสือ 25
  → Timer 25 นาที

• หยุดเวลา
  → หยุด timer

• สถิติการเรียน
  → รายงานเวลาเรียน
```

---

#### **5. Random Group Maker** 🎲
```
Impact: Medium
Complexity: Low
Time: 1 hour
```

**Features:**
- Shuffle class into groups
- Fair distribution
- Save group history

**Commands:**
```
• สุ่มกลุ่ม 5
  → แบ่ง 5 กลุ่ม

• สุ่มคู่
  → จับคู่สุ่ม
```

---

#### **6. Food Menu Randomizer** 🍔
```
Impact: Medium (fun!)
Complexity: Very Low
Time: 30 minutes
```

**Features:**
- Random lunch suggestions
- Filter by budget
- Add custom restaurants

**Commands:**
```
• กินอะไรดี
  → แนะนำอาหารสุ่ม

• อาหารงบ 50
  → อาหารไม่เกิน 50 บาท
```

---

#### **7. Birthday Tracker** 🎂
```
Impact: Medium
Complexity: Low
Time: 2 hours
```

**Features:**
- Store classmates' birthdays
- Auto-remind upcoming birthdays
- Birthday countdown

**Commands:**
```
• วันเกิด เพิ่ม [ชื่อ] [วันที่]
  → บันทึกวันเกิด

• วันเกิดใกล้เข้า
  → แสดงวันเกิดที่จะมาถึง
```

---

### **Tier 3: Nice to Have** ⭐⭐⭐

#### **8. Vocabulary Builder** 📖
- Save new words
- Daily word quiz
- Flashcard system

#### **9. Goal Tracker** 🎯
- Set academic goals
- Track progress
- Motivation quotes

#### **10. Class Poll/Vote** 🗳️
- Create simple polls
- Anonymous voting
- Results visualization

---

## 🎯 **Recommended Implementation Order**

### **Phase 1: Quick Wins (Week 1-2)**
```
1. Food Menu Randomizer     (30 min)  ← START HERE
2. Random Group Maker       (1 hour)
3. Grade Calculator         (2 hours) ← HIGH VALUE
```

### **Phase 2: High Value (Week 3-4)**
```
4. Quick Notes              (3 hours)  ← VERY USEFUL
5. Expense Tracker          (4 hours)  ← HIGH DEMAND
6. Study Timer              (2 hours)
```

### **Phase 3: Nice to Have (Week 5-6)**
```
7. Birthday Tracker         (2 hours)
8. Vocabulary Builder       (3 hours)
9. Goal Tracker             (3 hours)
10. Class Poll              (4 hours)
```

---

## 📝 **Implementation Template**

### **For ANY new feature, follow this structure:**

#### **1. Design Overview**
```
Feature Name: [Name]
File: [filename].py
Dependencies: [list]
Database Collections: [if needed]
```

#### **2. File Structure**
```python
# [feature_name].py
"""
Feature description
"""

# Imports
from typing import ...
import ...

# Constants
CONSTANT_NAME = ...

# Data Structures
@dataclass
class ...

# Core Logic
def main_function(...):
    ...

# Command Handlers
def handle_command(user_message: str) -> str:
    ...

# Message Formatting
def format_output(...) -> str:
    ...

# Integration
def get_commands_list():
    return [...]

def get_help_text() -> str:
    return "..."

# Testing
if __name__ == "__main__":
    # Unit tests
    ...
```

#### **3. Integration Steps**

**Step 1: Create feature file**
```bash
touch [feature_name].py
# Write code
```

**Step 2: Update handlers.py**
```python
# Import
from [feature_name] import get_commands_list, ServiceClass

# Initialize (in handle_message or at top)
service = ServiceClass(db)

# Add commands
COMMANDS += get_commands_list(service)
```

**Step 3: Update config.py (if needed)**
```python
# Add constants
FEATURE_ENABLED = True
FEATURE_SETTINGS = {...}
```

**Step 4: Update help text**
```python
# In features.py -> get_help_message()
help_text += get_feature_help_text()
```

#### **4. Testing Checklist**
```
□ Unit tests pass
□ Command works in LINE
□ Error handling works
□ Edge cases handled
□ Performance acceptable
□ No breaking changes
□ Documentation updated
```

---

## 🔧 **Design Principles**

### **1. Don't Break Existing Features**
```python
# ✅ Good: Add new commands
COMMANDS += new_commands

# ❌ Bad: Replace COMMANDS
COMMANDS = new_commands  # This breaks everything!
```

### **2. Follow Existing Structure**
```python
# ✅ Good: Match existing pattern
def get_new_feature_message(user_message: str = "") -> TextMessage:
    return TextMessage(text="...")

# ❌ Bad: Different return type
def get_new_feature_message(user_message: str) -> dict:
    return {"text": "..."}
```

### **3. Reuse Utilities**
```python
# ✅ Good: Use existing database
from main import db

# ✅ Good: Use existing logger
from config import logger

# ❌ Bad: Create new connections
import firebase_admin  # Already initialized!
```

### **4. Handle Errors Gracefully**
```python
# ✅ Good: Try-except with user-friendly messages
try:
    result = calculate_something()
    return f"✅ {result}"
except ValueError as e:
    logger.error(f"Calculation error: {e}")
    return "❌ ข้อมูลไม่ถูกต้อง กรุณาลองใหม่"
except Exception as e:
    logger.exception("Unexpected error")
    return "❌ เกิดข้อผิดพลาด"

# ❌ Bad: Let errors crash
result = calculate_something()  # No error handling!
```

---

## 📊 **Feature Impact Matrix**

| Feature | Impact | Complexity | Time | Priority |
|---------|--------|------------|------|----------|
| Grade Calculator | ⭐⭐⭐⭐⭐ | Medium | 2h | P0 |
| Quick Notes | ⭐⭐⭐⭐⭐ | Medium | 3h | P0 |
| Expense Tracker | ⭐⭐⭐⭐⭐ | Medium | 4h | P1 |
| Study Timer | ⭐⭐⭐⭐ | Low | 2h | P1 |
| Food Randomizer | ⭐⭐⭐⭐ | Very Low | 30m | P1 |
| Random Groups | ⭐⭐⭐ | Low | 1h | P2 |
| Birthday Tracker | ⭐⭐⭐ | Low | 2h | P2 |
| Vocabulary Builder | ⭐⭐⭐ | Medium | 3h | P3 |
| Goal Tracker | ⭐⭐⭐ | Medium | 3h | P3 |
| Class Poll | ⭐⭐ | Medium | 4h | P3 |

---

## 🚀 **Quick Start: Adding Your First Feature**

### **Example: Food Menu Randomizer (30 minutes)**

#### **Step 1: Create feature file (5 min)**
```python
# food_randomizer.py
import random
from linebot.v3.messaging import TextMessage

RESTAURANTS = {
    'cheap': [
        '7-11 (30฿)',
        'ก๋วยเตี๋ยวลุง (35฿)',
        'ข้าวมันไก่ (40฿)',
    ],
    'medium': [
        'เทสโก้ (50฿)',
        'KFC (80฿)',
        'Pizza (100฿)',
    ],
    'expensive': [
        'ซูชิ (200฿)',
        'สเต็ก (300฿)',
    ]
}

def get_random_food(budget: str = 'medium') -> str:
    """Get random food suggestion"""
    foods = RESTAURANTS.get(budget, RESTAURANTS['medium'])
    return random.choice(foods)

def handle_food_command(user_message: str = "") -> TextMessage:
    """Handle: กินอะไรดี"""
    
    # Check budget
    if 'งบ' in user_message or 'บาท' in user_message:
        # Extract budget
        import re
        numbers = re.findall(r'\d+', user_message)
        if numbers:
            budget_amount = int(numbers[0])
            if budget_amount < 50:
                budget = 'cheap'
            elif budget_amount < 100:
                budget = 'medium'
            else:
                budget = 'expensive'
        else:
            budget = 'medium'
    else:
        budget = 'medium'
    
    food = get_random_food(budget)
    
    message = f"🍔 *วันนี้กินอะไรดี?*\n\n"
    message += f"แนะนำ: {food}\n\n"
    message += f"💡 Tip: พิมพ์ 'กินอะไรดี งบ 50' เพื่อกำหนดงบประมาณ"
    
    return TextMessage(text=message)

def get_food_commands():
    """Return commands for integration"""
    return [
        (("กินอะไรดี", "กินไร", "แนะนำอาหาร"), handle_food_command),
    ]
```

#### **Step 2: Integrate with handlers.py (10 min)**
```python
# In handlers.py

# Add import at top
from food_randomizer import get_food_commands

# Add to COMMANDS list (around line 200)
COMMANDS = [
    # ... existing commands ...
    
    # Food randomizer (NEW!)
    *get_food_commands(),
]
```

#### **Step 3: Test (5 min)**
```
1. Deploy code
2. Send: "กินอะไรดี"
   → Should get random food suggestion
3. Send: "กินอะไรดี งบ 30"
   → Should get cheap options
4. ✅ Done!
```

#### **Step 4: Document (10 min)**
```python
# Update help in features.py

help_text += """
🍔 อาหาร
- กินอะไรดี = แนะนำอาหารสุ่ม
- กินอะไรดี งบ 50 = กำหนดงบประมาณ
"""
```

---

## 🎯 **Success Metrics**

### **Before Adding Features:**
- Features: 15
- Commands: ~20
- User Satisfaction: Good

### **After Adding Top 5 Features:**
- Features: 20+ (+33%)
- Commands: ~35+ (+75%)
- User Satisfaction: Excellent
- Daily Active Users: +50%
- Messages per day: +100%

---

## 📚 **Resources & References**

### **Documentation:**
- LINE Bot SDK: https://github.com/line/line-bot-sdk-python
- Firebase: https://firebase.google.com/docs
- Flask: https://flask.palletsprojects.com/

### **Similar Projects:**
- Student Helper Bots
- Academic Planners
- Budget Trackers

---

## ✅ **Next Steps**

### **Immediate Actions:**
```
1. Review roadmap
2. Pick first feature (recommend: Food Randomizer)
3. Follow implementation template
4. Test thoroughly
5. Deploy
6. Gather feedback
7. Iterate
```

### **This Week:**
```
□ Implement Food Randomizer (30 min)
□ Implement Grade Calculator (2 hours)
□ Test both features
□ Deploy to production
□ Monitor usage
```

### **This Month:**
```
□ Add Quick Notes (3 hours)
□ Add Expense Tracker (4 hours)
□ Add Study Timer (2 hours)
□ Gather user feedback
□ Plan next features
```

---

## 🎉 **Conclusion**

MTC Assistant มีศักยภาพสูงมากในการเพิ่มฟีเจอร์!

**Key Takeaways:**
1. **Start Small:** Food Randomizer (30 min)
2. **High Value First:** Grade Calculator (2 hours)
3. **User Feedback:** Listen and iterate
4. **Don't Break:** Follow existing patterns
5. **Test Everything:** Before deploying

**Your bot is already excellent (8.5/10). With 5-10 more features, it could be 10/10!** 🚀

---

**Roadmap Created:** January 11, 2026  
**Last Updated:** April 26, 2026  
**Author:** Claude AI (Software Architect)  
**Status:** Active — มี features ใหม่ที่ทำได้อีกเยอะมาก

**Let's build amazing features together! 💪**

---

## 🆕 Roadmap 2026 — Modern AI & UX Ideas

หลังจากบอทมีระบบหลังบ้านครบแล้ว (Firebase, Blacklist, Impersonate, Exam Simulator, Smart Calc, Grade Calculator) ขั้นต่อไปคือยกระดับด้วย AI ที่ลึกขึ้นและ UX ที่ทันสมัย

### Tier 0: AI-First Features (ใหม่ล่าสุด) 🚀

#### A. Personal AI Memory (Conversational Context) 🧠

- Value: AI จำชื่อ/วิชาที่ผู้ใช้สนใจ/บทสนทนาเดิมได้
- Impact: Game-changer — บอทรู้สึกเหมือนเพื่อนจริง
- Complexity: Medium-High | Time: 4-6 hours
- Tech: เก็บ `conversation_history` ใน Firestore per-user + ส่ง context window ไปกับทุก Gemini call (มี TTL เพื่อลดต้นทุน)

#### B. Document/PDF Q&A 📄

- Value: ส่งสไลด์/ชีท PDF เข้ามา → ถามตอบจากเนื้อหาในไฟล์ได้
- Impact: Very High (อ่านชีทก่อนสอบ)
- Complexity: High | Time: 4-12 hours
- Tech: Gemini Files API รับ PDF ตรงๆ → ส่งคำถาม + file_uri → ได้คำตอบ (ไม่ต้องทำ RAG เอง)

#### C. Image OCR + Math Solver 📸

- Value: ถ่ายโจทย์เลข/รูปกระดานส่งมา → AI อ่านโจทย์ + อธิบายวิธีทำ
- Impact: Very High (ใช้บ่อยตอนทำการบ้าน)
- Complexity: Medium | Time: 3-4 hours
- Tech: รับ `ImageMessage` → download content → ส่งให้ Gemini Vision พร้อม prompt เพื่อนสอนเพื่อน

#### D. Voice Message Support 🎙️

- Value: ส่งเสียงทักได้ (พิมพ์ไม่ทันตอนเรียน)
- Impact: Medium-High | Complexity: Medium | Time: 3-4 hours
- Flow: AudioMessage → Gemini Audio → transcript → handle เหมือน text ปกติ

---

### Tier 0.5: Smart Reminders & Automation ⏰

#### E. Smart Homework Reminder

- Value: เตือนการบ้านอัตโนมัติ 1 วันก่อนส่ง / 3 ชม.ก่อนส่ง
- Impact: Very High (ลืมส่ง = เรื่องใหญ่) | Time: 4-6 hours
- Note: `broadcast.broadcast_homework_reminder()` มีโครงไว้แล้ว ขาดแค่ scheduler (APScheduler หรือ external cron)

#### F. Class Schedule Push Notifications 🔔

- Value: Push เตือน 5 นาทีก่อนคาบเริ่ม + บอกห้อง
- Impact: High | Complexity: Medium | Time: 3-4 hours

#### G. Exam Countdown Daily Push 📅

- Value: ทุกเช้า 7 โมงเตือนเหลือกี่วันก่อนสอบ
- Impact: Medium-High | Complexity: Low | Time: 1-2 hours

---

### Tier 1.5: Productivity & Collaboration 🤝

#### H. Group Project Tracker 👥

- Value: สร้างกลุ่ม → assign tasks → mark done → สรุปสถานะ
- Impact: Medium | Complexity: Medium-High | Time: 6-8 hours

#### I. Shared Class Resources Library 📚

- Value: เพื่อนๆ แชร์ลิงก์ชีท/วิดีโอเข้าคลังกลาง — ค้นหาตามวิชา/แท็กได้
- Impact: High | Complexity: Medium | Time: 4 hours

#### J. Quick Notes / Birthday Tracker / Class Poll

- ดูรายละเอียดใน Tier 1-3 ด้านบน — ยังไม่ได้ทำ

---

### Tier 2.5: Admin & Operations 🛠️

#### K. Web Admin Dashboard 🖥️

- Value: เว็บจัดการ users/blacklist/broadcast แทนพิมพ์ใน LINE
- Impact: High | Complexity: High | Time: 12-16 hours
- Tech: Flask blueprint + Tailwind + simple admin auth

#### L. Analytics Dashboard 📊

- Value: กราฟ DAU / commands ที่นิยม / response time
- Impact: Medium | Complexity: Medium | Time: 4-6 hours
- Tech: Chart.js ที่ `/admin/stats` หรือเชื่อม Grafana จาก `/metrics`

#### M. Auto-recovery & Self-healing 🩺

- Value: บอทตรวจตัวเองเป็นระยะ (Firebase reconnect, Gemini quota) แล้ว auto-fix
- Impact: High (uptime ดีขึ้นมาก) | Time: 4 hours
- Note: ส่วน Firebase reconnect ทำแล้วใน `main.py` (background daemon thread)

---

### Tier 3.5: Engagement & Fun 🎮

#### N. Daily Quote/Motivation 💭

- Value: ส่งคำคม/ข้อคิดทุกเช้า — เด็ก ม.ปลายเครียด
- Complexity: Very Low | Time: 1 hour

#### O. Streak System 🔥

- Value: นับวันที่ใช้บอทต่อเนื่อง — gamify การใช้
- Impact: Medium-High | Time: 2-3 hours

#### P. Achievements/Badges 🏆

- Value: รางวัลเมื่อทำการบ้านครบ 10 ชิ้น / สอบจำลองครบ X ครั้ง
- Impact: Medium | Time: 4 hours

#### Q. Anonymous Confession Box 🤫

- Value: ระบบแชร์เรื่องลับๆ แบบไม่เปิดเผยตัวตน (admin คัดกรอง)
- Impact: Medium | Time: 3-4 hours
- ⚠️ ต้องมี content moderation จริงจัง (เสี่ยง bullying)

---

### Tier 4: Infrastructure Polish 🏗️

#### R. Unit & Integration Tests

- Value: ป้องกัน regression เมื่อเพิ่ม feature ใหม่
- Impact: High (long-term) | Time: 6-8 hours
- Tech: pytest + responses (mock LINE API) + firebase-admin offline mode

#### S. CI/CD Pipeline (GitHub Actions)

- Value: รัน tests + lint อัตโนมัติทุก push
- Impact: Medium-High | Time: 2-3 hours

#### T. Sentry Error Tracking

- Value: เห็น error ทุกตัวใน production พร้อม stack trace
- Impact: High (debugging) | Complexity: Very Low | Time: 30 min
- Tech: `sentry-sdk[flask]` — แค่เพิ่ม init บรรทัดเดียว

#### U. Structured Logging (JSON logs)

- Value: ค้นหา/filter logs ใน Render ได้ง่ายขึ้น
- Impact: Medium | Time: 1-2 hours
- Tech: `structlog` หรือ `python-json-logger`

#### V. Caching Layer (Redis or in-memory LRU)

- Value: Gemini responses ที่เหมือนกันใช้ cache → ลด cost + เร็วขึ้น
- Impact: High (cost optimization) | Time: 3-4 hours

#### W. Type Hints + mypy

- Value: เจอ bug จาก type mismatch ก่อน deploy
- Impact: Medium | ongoing งาน

---

## 🎯 Recommended Next 3 Features (อัปเดต Apr 2026)

จากสภาพปัจจุบัน (Firebase ทำงานแล้ว, ระบบหลังบ้านครบ) แนะนำลำดับนี้:

1. **Sentry Error Tracking** (30 นาที) — investment น้อยมาก แต่ debugging ดีขึ้นทันที
2. **Image OCR + Math Solver** (3-4 ชม.) — high impact + ใช้ Gemini Vision ที่ใช้อยู่แล้ว
3. **Smart Homework Reminder** (4-6 ชม.) — โครงในโค้ดมีแล้ว ขาดแค่ scheduler

หลังจากนั้นค่อยขยับไปทำ **Personal AI Memory** + **Web Admin Dashboard** เป็น big feature ถัดไป

---
