# handlers.py - INTEGRATION SNIPPET for Improved Grade Calculator
# ============================================================================
# ADD THIS to your handlers.py
# ============================================================================

# In the handle_message function, UPDATE the grade calculator section:

# ============================================================================
# GRADE CALCULATOR INTEGRATION (IMPROVED - with user_id support)
# ============================================================================

def handle_message(event):
    """Handle incoming text messages"""
    user_text = getattr(event.message, "text", "")
    user_message = user_text.strip()
    
    if not user_message:
        reply_to_line(event.reply_token, [TextMessage(text=MESSAGES["INVALID_MESSAGE"])])
        return
    
    # Get user ID
    user_id = None
    try:
        user_id = event.source.user_id if hasattr(event, "source") else None
    except Exception:
        user_id = None
    
    if not user_id:
        user_id = f"anon-{request.remote_addr or 'unknown'}"
    
    # ... [rest of your code] ...
    
    # ========================================================================
    # GRADE CALCULATOR COMMANDS (UPDATED)
    # ========================================================================
    
    message_lower = user_message.lower()
    
    # Session-based GPA commands
    if any(cmd in message_lower for cmd in ['เริ่ม gpa', 'start gpa']):
        reply_message = TextMessage(text=get_grade_calculator_response(user_message, user_id))
        reply_to_line(event.reply_token, [reply_message])
        return
    
    if any(cmd in message_lower for cmd in ['เพิ่มวิชา', 'add subject']):
        reply_message = TextMessage(text=get_grade_calculator_response(user_message, user_id))
        reply_to_line(event.reply_token, [reply_message])
        return
    
    if any(cmd in message_lower for cmd in ['ดู gpa', 'show gpa', 'สถานะ gpa']):
        reply_message = TextMessage(text=get_grade_calculator_response(user_message, user_id))
        reply_to_line(event.reply_token, [reply_message])
        return
    
    if any(cmd in message_lower for cmd in ['ยกเลิก gpa', 'cancel gpa']):
        reply_message = TextMessage(text=get_grade_calculator_response(user_message, user_id))
        reply_to_line(event.reply_token, [reply_message])
        return
    
    # Regular GPA calculation (all formats)
    if 'คำนวณ gpa' in message_lower or 'gpa' in message_lower or 'เกรดเฉลี่ย' in message_lower:
        reply_message = TextMessage(text=get_grade_calculator_response(user_message, user_id))
        reply_to_line(event.reply_token, [reply_message])
        return
    
    # Score to grade
    if 'คำนวณเกรด' in message_lower:
        reply_message = get_grade_calculator_response(user_message)  # No user_id needed
        reply_to_line(event.reply_token, [reply_message])
        return
    
    # ... [rest of your code] ...


# ============================================================================
# UPDATE features.py function signature
# ============================================================================

def get_grade_calculator_response(user_message: str, user_id: str = None) -> TextMessage:
    """
    Handle grade calculator commands
    NOW WITH user_id support for sessions!
    """
    try:
        from grade_calculator import (
            handle_score_to_grade_command,
            handle_gpa_calculation_command
        )
        
        message_lower = user_message.lower()
        
        # Check if it's score to grade
        if 'คำนวณเกรด' in message_lower and 'gpa' not in message_lower:
            result = handle_score_to_grade_command(user_message)
            return TextMessage(text=result)
        
        # GPA calculation (pass user_id for session support!)
        result = handle_gpa_calculation_command(user_message, user_id)
        return TextMessage(text=result)
        
    except ImportError:
        logger.error("grade_calculator.py not found")
        return TextMessage(text="❌ ระบบคำนวณเกรดยังไม่พร้อมใช้งาน")
    except Exception as e:
        logger.error(f"Grade calculator error: {e}")
        return TextMessage(text=f"❌ เกิดข้อผิดพลาด: {str(e)}")


# ============================================================================
# ALTERNATIVE: Simpler Integration (if you prefer)
# ============================================================================

# You can also use this simpler approach in COMMANDS list:

COMMANDS = [
    # ... other commands ...
    
    # Grade calculator commands
    (("เริ่ม gpa", "start gpa"), lambda msg: TextMessage(text=get_grade_calculator_response(msg, user_id))),
    (("เพิ่มวิชา", "add subject"), lambda msg: TextMessage(text=get_grade_calculator_response(msg, user_id))),
    (("คำนวณ gpa", "gpa", "เกรดเฉลี่ย"), lambda msg: TextMessage(text=get_grade_calculator_response(msg, user_id))),
    (("คำนวณเกรด",), lambda msg: get_grade_calculator_response(msg)),
    
    # ... other commands ...
]

# BUT: You need to make sure user_id is available in the lambda scope!
# This is trickier, so the explicit if-statements approach above is clearer.


# ============================================================================
# KEY CHANGES SUMMARY
# ============================================================================

"""
IMPORTANT CHANGES:

1. Pass user_id to get_grade_calculator_response()
   - BEFORE: get_grade_calculator_response(user_message)
   - AFTER:  get_grade_calculator_response(user_message, user_id)

2. Pass user_id to handle_gpa_calculation_command()
   - BEFORE: handle_gpa_calculation_command(user_message)
   - AFTER:  handle_gpa_calculation_command(user_message, user_id)

3. Add session commands to handlers
   - เริ่ม gpa
   - เพิ่มวิชา
   - ดู gpa
   - ยกเลิก gpa

4. Keep backwards compatibility
   - Old commands still work
   - Just with better parsing
"""

# ============================================================================
# TESTING
# ============================================================================

"""
Test these commands after deployment:

1. Step-by-step mode:
   User: เริ่ม GPA
   Bot: ✅ เริ่ม session...
   
   User: เพิ่มวิชา คณิต 3 4
   Bot: ✅ เพิ่ม คณิต แล้ว
   
   User: เพิ่มวิชา ฟิสิกส์ 3 3.5
   Bot: ✅ เพิ่ม ฟิสิกส์ แล้ว
   
   User: คำนวณ GPA
   Bot: 📊 ผลการคำนวณ GPA...

2. Pipe-separated mode:
   User: คำนวณ GPA | คณิต 3 4 | ฟิสิกส์ 3 3.5
   Bot: 📊 ผลการคำนวณ GPA...

3. Comma-separated mode:
   User: คำนวณ GPA คณิต 3 4, ฟิสิกส์ 3 3.5
   Bot: 📊 ผลการคำนวณ GPA...

4. Score to grade:
   User: คำนวณเกรด 85
   Bot: 📝 คำนวณเกรดจากคะแนน...
"""
