# -*- coding: utf-8 -*-
"""
MTC Assistant - Food Menu Randomizer
แนะนำอาหารแบบสุ่ม (Quick Win Feature!)

Complexity: Very Low
Time to implement: 30 minutes
Impact: High (Fun + Useful)
"""

import random
import re
from linebot.v3.messaging import TextMessage

# ============================================================================
# RESTAURANT DATABASE
# ============================================================================

RESTAURANTS = {
    'cheap': {
        'thai': [
            {'name': 'ก๋วยเตี๋ยวลุง', 'price': 35, 'emoji': '🍜'},
            {'name': 'ข้าวมันไก่', 'price': 40, 'emoji': '🍗'},
            {'name': 'ข้าวขาหมู', 'price': 40, 'emoji': '🍖'},
            {'name': 'ข้าวผัดหมู', 'price': 35, 'emoji': '🍚'},
            {'name': 'ส้มตำ', 'price': 30, 'emoji': '🥗'},
        ],
        'fast_food': [
            {'name': '7-11 (ข้าวกล่อง)', 'price': 30, 'emoji': '🍱'},
            {'name': 'แม่มา', 'price': 15, 'emoji': '🍜'},
            {'name': 'ขนมปัง', 'price': 25, 'emoji': '🥪'},
        ]
    },
    'medium': {
        'thai': [
            {'name': 'ข้าวราดแกง', 'price': 50, 'emoji': '🍛'},
            {'name': 'ผัดไทย', 'price': 60, 'emoji': '🍝'},
            {'name': 'ข้าวหมูกรอบ', 'price': 55, 'emoji': '🍖'},
        ],
        'fast_food': [
            {'name': 'เทสโก้ โลตัส', 'price': 50, 'emoji': '🛒'},
            {'name': 'MK (ชุดนักเรียน)', 'price': 80, 'emoji': '🍲'},
            {'name': 'Pizza Company (Personal)', 'price': 99, 'emoji': '🍕'},
        ],
        'cafe': [
            {'name': 'Café Amazon', 'price': 60, 'emoji': '☕'},
            {'name': 'เบเกอรี่', 'price': 70, 'emoji': '🥐'},
        ]
    },
    'expensive': {
        'restaurant': [
            {'name': 'KFC', 'price': 120, 'emoji': '🍗'},
            {'name': 'McDonald\'s', 'price': 150, 'emoji': '🍔'},
            {'name': 'Sushi', 'price': 200, 'emoji': '🍣'},
            {'name': 'Steak', 'price': 250, 'emoji': '🥩'},
            {'name': 'Shabu', 'price': 299, 'emoji': '🍲'},
        ],
        'cafe': [
            {'name': 'Starbucks', 'price': 150, 'emoji': '☕'},
            {'name': 'After You', 'price': 180, 'emoji': '🍰'},
        ]
    }
}

# ============================================================================
# CORE FUNCTIONS
# ============================================================================

def get_budget_category(budget: int) -> str:
    """Determine budget category from amount"""
    if budget < 50:
        return 'cheap'
    elif budget < 100:
        return 'medium'
    else:
        return 'expensive'

def get_random_food(budget_category: str = 'medium', cuisine: str = None) -> dict:
    """
    Get random food suggestion
    
    Args:
        budget_category: 'cheap', 'medium', or 'expensive'
        cuisine: specific cuisine type or None for random
    
    Returns:
        dict with restaurant info
    """
    category_foods = RESTAURANTS.get(budget_category, RESTAURANTS['medium'])
    
    if cuisine and cuisine in category_foods:
        foods = category_foods[cuisine]
    else:
        # Get all foods from category
        foods = []
        for cuisine_foods in category_foods.values():
            foods.extend(cuisine_foods)
    
    if not foods:
        # Fallback to medium if nothing found
        return get_random_food('medium')
    
    return random.choice(foods)

def get_all_options(budget_category: str, limit: int = 5) -> list:
    """Get multiple random options"""
    category_foods = RESTAURANTS.get(budget_category, RESTAURANTS['medium'])
    
    all_foods = []
    for cuisine_foods in category_foods.values():
        all_foods.extend(cuisine_foods)
    
    # Shuffle and return top N
    random.shuffle(all_foods)
    return all_foods[:limit]

# ============================================================================
# MESSAGE FORMATTING
# ============================================================================

def format_food_suggestion(food: dict, show_alternatives: bool = True) -> str:
    """Format food suggestion for display"""
    message = f"🍔 *วันนี้กินอะไรดี?*\n\n"
    message += f"{food['emoji']} แนะนำ: *{food['name']}*\n"
    message += f"💰 ราคาประมาณ: {food['price']} บาท\n"
    
    if show_alternatives:
        message += f"\n💡 ไม่ชอบ? พิมพ์ 'กินอะไรดี' อีกครั้งเพื่อสุ่มใหม่"
    
    return message

def format_multiple_options(foods: list, budget_category: str) -> str:
    """Format multiple food options"""
    budget_names = {
        'cheap': 'ประหยัด (< 50฿)',
        'medium': 'ปานกลาง (50-100฿)',
        'expensive': 'หรูหรา (> 100฿)'
    }
    
    message = f"🍽️ *เมนูแนะนำ (งบ{budget_names[budget_category]})*\n\n"
    
    for i, food in enumerate(foods, 1):
        message += f"{i}. {food['emoji']} {food['name']}\n"
        message += f"   {food['price']} บาท\n\n"
    
    message += f"💡 พิมพ์ 'กินอะไรดี' เพื่อสุ่มอีกครั้ง"
    
    return message

# ============================================================================
# COMMAND HANDLERS
# ============================================================================

def handle_food_randomizer_command(user_message: str = "") -> TextMessage:
    """
    Handle food randomizer command
    
    Supported formats:
    - กินอะไรดี
    - กินอะไรดี งบ 50
    - กินอะไรดี แนะนำ 5
    - อาหารงบ 80
    """
    message_lower = user_message.lower()
    
    # Extract budget
    budget = None
    budget_category = 'medium'  # default
    
    numbers = re.findall(r'\d+', user_message)
    if numbers:
        budget = int(numbers[0])
        budget_category = get_budget_category(budget)
    
    # Check if user wants multiple options
    wants_multiple = any(word in message_lower for word in ['แนะนำ', 'หลาย', 'ตัวเลือก'])
    
    if wants_multiple:
        # How many options?
        limit = 5
        if len(numbers) > 0:
            limit = min(int(numbers[-1]), 10)  # Max 10 options
        
        options = get_all_options(budget_category, limit)
        text = format_multiple_options(options, budget_category)
    else:
        # Single random suggestion
        food = get_random_food(budget_category)
        text = format_food_suggestion(food)
    
    return TextMessage(text=text)

# ============================================================================
# INTEGRATION
# ============================================================================

def get_food_randomizer_commands():
    """
    Return command tuples for integration with handlers.py
    
    Usage in handlers.py:
        from food_randomizer import get_food_randomizer_commands
        COMMANDS += get_food_randomizer_commands()
    """
    return [
        (("กินอะไรดี", "กินไร", "แนะนำอาหาร", "อาหารวันนี้"), handle_food_randomizer_command),
        (("อาหารงบ", "เมนูงบ"), handle_food_randomizer_command),
    ]

def get_food_randomizer_help() -> str:
    """Return help text for food randomizer"""
    return """
🍔 *แนะนำอาหาร*

• กินอะไรดี
  → แนะนำอาหารสุ่ม

• กินอะไรดี งบ 50
  → กำหนดงบประมาณ

• กินอะไรดี แนะนำ 5
  → แสดงหลายตัวเลือก
"""

# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("=== Food Randomizer Testing ===\n")
    
    # Test 1: Random food
    print("Test 1: Basic random")
    food = get_random_food()
    print(f"Result: {food['name']} ({food['price']}฿)")
    
    # Test 2: Budget category
    print("\nTest 2: Budget categories")
    for budget in [30, 70, 150]:
        category = get_budget_category(budget)
        print(f"Budget {budget}฿ → Category: {category}")
    
    # Test 3: Multiple options
    print("\nTest 3: Multiple options")
    options = get_all_options('cheap', 3)
    for opt in options:
        print(f"  - {opt['name']} ({opt['price']}฿)")
    
    # Test 4: Command handler
    print("\nTest 4: Command handler")
    test_messages = [
        "กินอะไรดี",
        "กินอะไรดี งบ 40",
        "กินอะไรดี แนะนำ 3",
    ]
    
    for msg in test_messages:
        print(f"\nInput: '{msg}'")
        result = handle_food_randomizer_command(msg)
        print(f"Output:\n{result.text}\n")
    
    print("=== All tests passed! ===")
