# smart_calc.py
# -*- coding: utf-8 -*-
"""
Smart Calculator with temporary variables
- calculate(expression: str) -> str
- supports assignments: x = 5
- special commands: "vars" -> list variables, "clearvars" -> clear variables
- Safe AST evaluation (whitelist)
"""

from __future__ import annotations
import ast
import operator as op
import math
import re
import sys
from collections import OrderedDict
from typing import Any, Dict, Optional

# ---------- ALLOWED OPERATIONS & FUNCTIONS ----------
_BIN_OPS = {
    ast.Add: op.add,
    ast.Sub: op.sub,
    ast.Mult: op.mul,
    ast.Div: op.truediv,
    ast.FloorDiv: op.floordiv,
    ast.Mod: op.mod,
    ast.Pow: op.pow,
}

_UNARY_OPS = {
    ast.UAdd: lambda x: x,
    ast.USub: lambda x: -x,
}

def _safe_factorial(n):
    """Factorial wrapper that rejects floats, negatives, and dangerously large inputs."""
    if not isinstance(n, (int, float)) or n != int(n):
        raise ValueError("factorial ต้องการเลขจำนวนเต็มเท่านั้น")
    n = int(n)
    if n < 0:
        raise ValueError("factorial ไม่รองรับจำนวนลบ")
    if n > 1000:
        raise ValueError("ตัวเลขใหญ่เกินไปสำหรับ factorial (สูงสุด 1000)")
    return math.factorial(n)

_ALLOWED_FUNCS: Dict[str, Any] = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "exp": math.exp,
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "degrees": math.degrees,
    "radians": math.radians,
    "factorial": _safe_factorial,
    "fact": _safe_factorial,
    "comb": getattr(math, "comb", None),
    "perm": getattr(math, "perm", None),
}

_ALLOWED_CONSTS: Dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau if hasattr(math, "tau") else math.pi * 2,
    "inf": math.inf,
}

# ---------- Per-user variable storage ----------
# Each user gets their own isolated namespace so User A's variables
# never bleed into User B's calculations.
_USER_VARS: OrderedDict = OrderedDict()
_USER_VARS_MAX = 500

def get_user_vars(user_id: str) -> Dict[str, float]:
    """Return (and lazily create) the variable namespace for a given user."""
    if user_id not in _USER_VARS:
        if len(_USER_VARS) >= _USER_VARS_MAX:
            _USER_VARS.popitem(last=False)  # evict oldest entry
        _USER_VARS[user_id] = {}
    else:
        _USER_VARS.move_to_end(user_id)  # mark as recently used
    return _USER_VARS[user_id]

# ---------- SAFE AST EVALUATOR ----------
class _SafeEvaluator(ast.NodeVisitor):
    def __init__(self, variables: Optional[Dict[str, Any]] = None):
        self.vars = variables or {}

    def visit(self, node):
        method = "visit_" + node.__class__.__name__
        visitor = getattr(self, method, None)
        if visitor is None:
            raise ValueError(f"ไม่อนุญาตให้ใช้: {node.__class__.__name__}")
        return visitor(node)

    def visit_Expression(self, node: ast.Expression):
        return self.visit(node.body)

    def visit_BinOp(self, node: ast.BinOp):
        left = self.visit(node.left)
        right = self.visit(node.right)
        op_type = type(node.op)
        if op_type in _BIN_OPS:
            return _BIN_OPS[op_type](left, right)
        raise ValueError(f"ไม่รองรับ operator: {op_type.__name__}")

    def visit_UnaryOp(self, node: ast.UnaryOp):
        operand = self.visit(node.operand)
        op_type = type(node.op)
        if op_type in _UNARY_OPS:
            return _UNARY_OPS[op_type](operand)
        raise ValueError(f"ไม่รองรับ unary operator: {op_type.__name__}")

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            func = _ALLOWED_FUNCS.get(func_name)
            if not func:
                raise ValueError(f"ฟังก์ชันไม่รองรับ: {func_name}")
            args = [self.visit(a) for a in node.args]
            if node.keywords:
                raise ValueError("ไม่รองรับ keyword arguments")
            return func(*args)
        raise ValueError("การเรียกฟังก์ชันแบบนี้ไม่ปลอดภัย")

    def visit_Name(self, node: ast.Name):
        # check variables first
        if node.id in self.vars:
            val = self.vars[node.id]
            if isinstance(val, (int, float)):
                return val
            raise ValueError(f"ค่าตัวแปรไม่รองรับ: {node.id}")
        if node.id in _ALLOWED_CONSTS:
            return _ALLOWED_CONSTS[node.id]
        if node.id in ("True", "False"):
            return True if node.id == "True" else False
        raise ValueError(f"ตัวแปรไม่อนุญาต: {node.id}")

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"ค่าประเภทไม่รองรับ: {type(node.value).__name__}")

    def visit_Num(self, node: ast.Num):  # for older pythons
        return node.n

    # forbid others
    def visit_List(self, node): raise ValueError("ไม่รองรับ list")
    def visit_Tuple(self, node): raise ValueError("ไม่รองรับ tuple")
    def visit_Dict(self, node): raise ValueError("ไม่รองรับ dict")
    def visit_Attribute(self, node): raise ValueError("ไม่อนุญาต attribute access")
    def visit_Subscript(self, node): raise ValueError("ไม่อนุญาต subscript")
    def visit_Lambda(self, node): raise ValueError("ไม่อนุญาต lambda")
    def visit_IfExp(self, node): raise ValueError("ไม่รองรับ conditional expression")
    def generic_visit(self, node): raise ValueError(f"ไม่อนุญาต node: {node.__class__.__name__}")

# ---------- PREPROCESS INPUT ----------
_PERCENT_RE = re.compile(r'(?P<num>(?:\d+\.\d+|\d+))%')
_FACT_PATTERN = re.compile(r'(?P<expr>(?:\d+(\.\d+)?|\([^()]*\)))!')

def _preprocess(expr: str) -> str:
    if not isinstance(expr, str):
        raise ValueError("expression ต้องเป็นสตริง")
    s = expr.strip()
    s = s.replace("×", "*").replace("·", "*").replace("÷", "/")
    s = s.replace("^", "**")
    while True:
        m = _PERCENT_RE.search(s)
        if not m:
            break
        num = m.group("num")
        s = s[:m.start()] + f"({num}/100)" + s[m.end():]
    while True:
        m = _FACT_PATTERN.search(s)
        if not m:
            break
        inner = m.group("expr")
        s = s[:m.start()] + f"fact({inner})" + s[m.end():]
    s = re.sub(r'(?<=\d),(?=\d)', '', s)
    return s

# ---------- RESULT FORMATTING ----------
def _format_result(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        rounded = round(value, 12)
        if abs(rounded - round(rounded)) < 1e-12:
            return str(int(round(rounded)))
        s = f"{rounded:.12f}".rstrip("0").rstrip(".")
        return s
    return str(value)

# ---------- VARIABLES API ----------
def list_vars(user_id: str = "global") -> Dict[str, str]:
    """Return the calling user's variables as name -> formatted value."""
    return {k: _format_result(v) for k, v in get_user_vars(user_id).items()}

def clear_vars(user_id: str = "global") -> None:
    """Clear only the calling user's variable namespace."""
    _USER_VARS.pop(user_id, None)

def set_var(name: str, value: float, user_id: str = "global") -> None:
    """Store a variable in the calling user's namespace."""
    get_user_vars(user_id)[name] = value

# ---------- MAIN CALCULATE FUNCTION ----------
_VAR_NAME_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')

def calculate(expression: str, user_id: str = "global") -> tuple:
    """
    Evaluate a math expression in the calling user's isolated variable namespace.

    Returns:
        (result_string: str, is_numeric: bool)
        is_numeric=True  → result is a plain number (caller may prefix "Result:")
        is_numeric=False → result is a status/error message
    """
    if not expression or not isinstance(expression, str):
        return "กรุณาใส่สมการ เช่น: 12*(5+3)^2", False

    expr = expression.strip()
    user_vars = get_user_vars(user_id)

    # special commands
    if expr.lower() == "vars":
        vars_map = list_vars(user_id)
        if not vars_map:
            return "ไม่มีตัวแปรถูกเก็บไว้", False
        return "\n".join([f"{k} = {v}" for k, v in vars_map.items()]), False
    if expr.lower() == "clearvars":
        clear_vars(user_id)
        return "ลบตัวแปรทั้งหมดแล้ว", False

    # handle assignment: only single '=' allowed
    if "=" in expr:
        parts = expr.split("=")
        if len(parts) != 2:
            return "ข้อผิดพลาด: รูปแบบการกำหนดตัวแปรไม่ถูกต้อง (ใช้ได้เช่น x = 5)", False
        var_name = parts[0].strip()
        rhs = parts[1].strip()
        if not _VAR_NAME_RE.match(var_name):
            return "ข้อผิดพลาด: ชื่อตัวแปรไม่ถูกต้อง (ต้องขึ้นต้นด้วยตัวอักษรหรือ _ และมีตัวอักษร/ตัวเลข/_)", False
        if var_name in _ALLOWED_FUNCS or var_name in _ALLOWED_CONSTS:
            return f"ข้อผิดพลาด: ไม่สามารถใช้ชื่อนี้ ({var_name}) เป็นชื่อตัวแปร", False
        try:
            pre = _preprocess(rhs)
            node = ast.parse(pre, mode="eval")
            evaluator = _SafeEvaluator(variables=user_vars)
            value = evaluator.visit(node)
            if not isinstance(value, (int, float)):
                return "ข้อผิดพลาด: ผลลัพธ์ที่ได้ไม่ใช่ตัวเลข", False
            set_var(var_name, float(value), user_id)
            return f"{var_name} = {_format_result(value)}", False
        except Exception as e:
            msg = str(e)
            if "division by zero" in msg:
                return "อ๊ะ! ในทางคณิตศาสตร์เราหารด้วยศูนย์ไม่ได้น้าา 🚫 ลองแก้ตัวเลขดูใหม่นะครับ", False
            if "math domain error" in msg:
                return "ตัวเลขนี้มันหลุดขอบจักรวาลคณิตศาสตร์ไปหน่อยฮะ 🌌 ลองเปลี่ยนค่าดูน้า", False
            return f"แงงง ระบบคำนวณไม่ถูกเลยฮะ เช็คสมการให้อีกทีได้มั้ยเอ่ย? 🧐 ({msg})", False

    # otherwise evaluate expression with current user's vars
    try:
        pre = _preprocess(expr)
        node = ast.parse(pre, mode="eval")
        evaluator = _SafeEvaluator(variables=user_vars)
        result = evaluator.visit(node)
        return _format_result(result), True
    except Exception as e:
        msg = str(e)
        if "division by zero" in msg:
            return "อ๊ะ! ในทางคณิตศาสตร์เราหารด้วยศูนย์ไม่ได้น้าา 🚫 ลองแก้ตัวเลขดูใหม่นะครับ", False
        if "math domain error" in msg:
            return "ตัวเลขนี้มันหลุดขอบจักรวาลคณิตศาสตร์ไปหน่อยฮะ 🌌 ลองเปลี่ยนค่าดูน้า", False
        return f"แงงง ระบบคำนวณไม่ถูกเลยฮะ เช็คสมการให้อีกทีได้มั้ยเอ่ย? 🧐 ({msg})", False

# ---------- smart_calculate wrapper ----------
def smart_calculate(expression: str, user_id: str = "global") -> str:
    """
    Public wrapper called by handlers.py.
    Passes user_id so each user has an isolated variable namespace.
    Prefixes numeric results with an emoji label for readability.
    """
    result, is_numeric = calculate(expression, user_id)
    return f"✨ คำตอบคือ: {result} 🤓" if is_numeric else result

# ---------- CLI ----------
def _cli_main():
    if len(sys.argv) < 2:
        print("Usage: python smart_calc.py \"<expression>\"")
        print("Examples:")
        print("  python smart_calc.py \"x = 5\"")
        print("  python smart_calc.py \"x * 2\"")
        print("  python smart_calc.py \"vars\"")
        sys.exit(0)
    expr = " ".join(sys.argv[1:])
    print("Expression:", expr)
    result, _ = calculate(expr)
    print("Result:", result)

if __name__ == "__main__":
    _cli_main()