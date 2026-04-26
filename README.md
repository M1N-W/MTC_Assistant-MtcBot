<div align="center">

# 🤖 MTC Assistant

**LINE Bot ผู้ช่วยอัจฉริยะสำหรับนักเรียน**

พัฒนาโดยนักเรียนชั้น ม.5/2 โรงเรียนเบญจมราชูทิศ  
เพื่อช่วยเหลือเพื่อนๆ ในการจัดการชีวิตประจำวันในโรงเรียน

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-Gunicorn_gthread-green?logo=flask)
![LINE](https://img.shields.io/badge/LINE-Messaging_API-00C300?logo=line)
![Firebase](https://img.shields.io/badge/Firebase-Firestore-orange?logo=firebase)
![Gemini](https://img.shields.io/badge/Google-Gemini_AI-4285F4?logo=google)

</div>

---

## 💭 เรื่องราว

เริ่มจากความต้องการมี Personal Assistant ที่เข้าใจชีวิตนักเรียนจริงๆ ไม่ใช่แค่บอทตอบคำถาม แต่เป็น **"เพื่อนติวเตอร์/หัวหน้าห้องสุดแสนดี"** ที่คอยช่วยเหลือตลอด 24 ชั่วโมง พร้อม **"โหมดผู้ช่วยสายลับ 🕵️‍♂️"** สำหรับระบบหลังบ้านของแอดมิน

> ✨ ตอนนี้มีเพื่อนๆ กว่า **40+ คน** ใช้งานอยู่จริง และ Active User **9 คน**

---

## 🎯 ความสามารถ (Features)

### 📚 เรื่องเรียน & สอบ

| ฟีเจอร์ | คำอธิบาย |
|---|---|
| **ตารางเรียน** | ดูว่าเรียนอะไรต่อไป อยู่ห้องไหน อัปเดตแบบเรียลไทม์ |
| **นับถอยหลังสอบ** | บอกเหลืออีกกี่วันก่อนสอบกลาง/ปลายภาค |
| **Exam Simulator** | จำลองการทำข้อสอบ ม.ปลาย พร้อมเฉลยจาก Gemini AI |
| **คำนวณเกรด & GPA** | Session-based — เพิ่มวิชาทีละตัว หรือใส่ครั้งเดียว |
| **จัดการการบ้าน** | เพิ่ม/ดู/ลบการบ้าน พร้อมระบบแจ้งเตือนอัตโนมัติ |

### ⏰ จัดการเวลา

- **คาบต่อไป** — บอกว่าจะเรียนอะไร เหลือเวลาอีกกี่นาที
- **เช็คเวลา** — แสดงเวลาที่เหลือจนถึงคาบถัดไปแบบ Real-time

### 🤖 AI & Tools

- **Gemini AI Chat** — ตอบคำถามและอธิบายบทเรียนได้เกือบทุกเรื่อง (Dual-model: Primary + Fallback)
- **Smart Calc** — คำนวณสมการคณิตศาสตร์ด้วย Safe AST Evaluator รองรับตัวแปร/ฟังก์ชัน/เปอร์เซ็นต์
- **ค้นหาเพลง & อาหาร** — หาเพลงใน YouTube และสุ่มเมนูอาหาร

### 👨‍💼 สำหรับ Admin (โหมดสายลับ 🕵️‍♂️)

- **Impersonate** — ส่งข้อความในนามบอทไปหาเป้าหมาย (มี Retry + Exponential Backoff)
- **Broadcast** — กระจายประกาศด่วนถึงทุกคนในห้องพร้อม Rate Limit Protection
- **User Blacklist** — ระบบแบน/ปลดแบนผู้ใช้ที่ก่อกวน (Firestore-backed + In-memory Cache)
- **สถิติ** — เช็คยอดผู้ใช้และประวัติการทำภารกิจ

---

## 🎮 วิธีใช้งาน

### คำสั่งทั่วไป

```
งาน / ใบงาน          → ดูใบงาน
ตารางเรียน            → ดูตารางสอน
คาบต่อไป              → ดูว่าเรียนอะไรต่อ
สอบ / วันสอบ          → นับถอยหลังวันสอบ
สอบจำลอง              → เริ่มทำข้อสอบจำลอง
คำนวณเกรด             → เข้าสู่ระบบคำนวณเกรด/GPA
การบ้าน               → ดูการบ้านทั้งหมด
ลิงก์                 → เมนูลิงก์สำคัญ (Flex Message)
help / ช่วยเหลือ       → ดูคำสั่งทั้งหมด
```

### จัดการการบ้าน (Interactive)

```
สั่งการบ้าน   → เริ่ม Session เลือกวิชา → รายละเอียด → กำหนดส่ง
การบ้าน        → ดูการบ้านทั้งหมด
ยกเลิกการบ้าน  → ยกเลิก Session ที่ค้างอยู่
```

### Smart Calc

```
2^10 + sqrt(144)        → คำนวณสมการ
x = 5                   → กำหนดตัวแปร
x * 2 + pi              → ใช้ตัวแปรและค่าคงที่
vars                    → ดูตัวแปรที่เก็บไว้
clearvars               → ลบตัวแปรทั้งหมด
```

### คำนวณ GPA

```
เริ่ม GPA                              → เริ่ม Session ทีละวิชา
เพิ่มวิชา คณิต 3 4                     → เพิ่มวิชา [ชื่อ] [หน่วยกิต] [เกรด]
คำนวณ GPA                             → ดูผล
คำนวณ GPA | คณิต 3 4 | ฟิสิกส์ 3 3.5  → ใส่ครั้งเดียวคั่นด้วย |
คำนวณเกรด 85                           → แปลงคะแนน → เกรด
```

### คำสั่ง Admin (เฉพาะผู้ดูแล)

```
admin                             → ดูคำสั่งแอดมินทั้งหมด
ประกาศ [ข้อความ]                  → กระจายข่าวถึงทุกคน
ส่งถึง [user_id] [ข้อความ]        → ส่งข้อความสวมรอย
ทดสอบส่ง [ข้อความ]               → ทดสอบระบบส่งหาตัวเอง
ดูผู้ใช้                          → ดูรายชื่อเป้าหมายล่าสุด
แบน [user_id] [เหตุผล]            → แบนผู้ใช้
ปลดแบน [user_id]                  → ปลดแบนผู้ใช้
รายชื่อแบน                        → ดูแฟ้มบัญชีดำ
สถิติแบน                          → ดูสถิติการแบน
สถิติประกาศ                       → ดูรายงาน Broadcast
จำนวนผู้ใช้                       → เช็คจำนวนผู้ใช้ทั้งหมด
```

---

## 🛠️ เทคโนโลยี & สถาปัตยกรรม

| Stack | รายละเอียด |
|---|---|
| **Python 3.11** | ภาษาหลัก |
| **Flask + Gunicorn (`gthread`)** | Web framework — ใช้ `gthread` แทน `gevent` เพื่อแก้ปัญหา Firebase gRPC Deadlock |
| **LINE Messaging API v3** | SDK สำหรับ Webhook, Reply, Push Message |
| **Firebase Firestore** | ฐานข้อมูล NoSQL สำหรับ homework, users, blacklist, broadcast history |
| **Google Gemini API** | Dual-model (Primary + Fallback) + Signal-based Timeout |
| **Render.com** | Cloud Hosting (Auto-deploy จาก `render.yaml`) |

### ทำไมถึงเปลี่ยนจาก `gevent` → `gthread`

Gevent monkey-patches threading primitives ซึ่งทำให้ Firebase gRPC client เกิด Deadlock ใน Gunicorn worker ส่งผลให้ request timeout บ่อย การเปลี่ยนเป็น `gthread` (OS threads จริง) แก้ปัญหานี้ได้โดยไม่ต้องแก้โค้ดส่วนอื่น

---

## 📁 โครงสร้างโค้ด

```
mtc-assistant/
├── main.py              # Flask app, health check, system init
├── config.py            # Constants, ENV vars, MESSAGES, SCHEDULE, EXAM_DATES
├── handlers.py          # Webhook handler, routing, rate limiting, homework session
├── features.py          # Core features (ตารางเรียน, Gemini AI, DB helpers)
├── exam_simulator.py    # Exam simulator — generate/answer/score ด้วย Gemini AI
├── grade_calculator.py  # GPA calculator — multi-format input, session-based
├── smart_calc.py        # Safe AST math evaluator, per-user variable namespace
├── broadcast.py         # Push message, broadcast, homework reminder, stats
├── user_blacklist.py    # Firestore-backed blacklist, in-memory cache
├── admin_impersonate.py # Admin impersonate — push message with retry mechanism
├── food_randomizer.py   # สุ่มเมนูอาหาร
├── requirements.txt     # Python dependencies
└── render.yaml          # Render deployment config (gthread worker)
```

---

## 🚀 การติดตั้ง

### 1. Clone โปรเจกต์

```bash
git clone https://github.com/yourusername/mtc-assistant.git
cd mtc-assistant
```

### 2. ติดตั้ง dependencies

```bash
pip install -r requirements.txt
```

### 3. ตั้งค่า Environment Variables

```bash
export CHANNEL_ACCESS_TOKEN="your_line_access_token"
export CHANNEL_SECRET="your_line_channel_secret"
export GEMINI_API_KEY_PRIMARY="your_gemini_primary_key"
export GEMINI_API_KEY_SECONDARY="your_gemini_secondary_key"   # fallback (optional)
export GEMINI_MODEL_PRIMARY="gemini-2.0-flash"
export GEMINI_MODEL_SECONDARY="gemini-2.5-flash-preview-04-17"
export ADMIN_USER_IDS="U1234567890abcdef"   # LINE User ID ของแอดมิน
export RATE_LIMIT_MAX="6"
export RATE_LIMIT_WINDOW="60"
```

### 4. Deploy บน Render

1. สมัครบัญชี [render.com](https://render.com/)
2. เชื่อมต่อ GitHub repo
3. Render จะอ่าน `render.yaml` และตั้งค่า Web Service ให้อัตโนมัติ
4. ตั้งค่า Environment Variables ใน Render Dashboard
5. Bot จะรันที่ `https://mtcbot.onrender.com`

---

## 📊 API Endpoints

| Method | Path | คำอธิบาย |
|---|---|---|
| `GET` | `/` | Health check และ status |
| `POST` | `/callback` | LINE Webhook endpoint |
| `GET` | `/healthz` | Detailed health check (JSON) |
| `GET` | `/metrics` | Performance metrics |

---

## 🎓 สิ่งที่เรียนรู้จากโปรเจกต์

### Technical Skills
- **System Architecture** — แยก Module ตาม Separation of Concerns อย่างชัดเจน
- **Concurrency & Deadlock** — วิเคราะห์และแก้ปัญหา gRPC + gevent conflict ด้วย gthread
- **UX/UI Copywriting** — ออกแบบ Tone of Voice ของแชทบอทให้ครอบคลุมทุก Module
- **Safe Code Execution** — สร้าง AST-based math evaluator ที่ป้องกัน code injection
- **API & Webhook** — LINE Messaging API v3, Google Gemini API, Firebase Firestore
- **Retry & Backoff** — Exponential backoff สำหรับ rate-limited API calls

### Soft Skills
- การแก้ปัญหาและ Debugging ระดับ Production
- การทำงานร่วมกับ AI (Claude + Gemini) ในฐานะ Dev Partner
- การบริหารโปรเจกต์และวาง Feature Roadmap

---

## 📈 Roadmap

- [x] ระบบตารางเรียนและแจ้งเตือน
- [x] ระบบการบ้าน (Firebase)
- [x] AI Integration (Gemini Dual-model)
- [x] ระบบ Admin & Broadcast
- [x] เครื่องคิดเลขอัจฉริยะ (Smart Calc + AST Parser)
- [x] คำนวณเกรดและ GPA (Session-based)
- [x] ระบบข้อสอบจำลอง (Exam Simulator)
- [x] ระบบแบนผู้ใช้ (Blacklist + Firestore cache)
- [x] ระบบสวมรอย (Admin Impersonate + Retry)
- [x] UX Copywriting Refactor (Persona ครบทุก Module)
- [x] Firebase Credentials via ENV (ไม่ต้องแนบ key เข้า repo)
- [x] Log Hygiene (ลบ warning ที่ทำให้สับสนตอน startup)
- [ ] Food Randomizer (ระบบแนะนำอาหาร)
- [ ] Quick Notes (โน้ตด่วนพร้อม tag)
- [ ] Expense Tracker (จดรายรับ-รายจ่าย)
- [ ] Study Timer (Pomodoro 25/5)
- [ ] Birthday Tracker (เก็บ + แจ้งเตือนวันเกิดเพื่อนในห้อง)
- [ ] Random Group Maker (สุ่มจับกลุ่ม/คู่)
- [ ] Vocabulary Builder (คลังศัพท์ + Flashcard)
- [ ] Goal Tracker (เป้าหมายการเรียน + ความคืบหน้า)
- [ ] Class Poll/Vote (โพลในห้องแบบไม่เปิดเผยตัวตน)
- [ ] Smart Homework Reminder (เตือนการบ้านล่วงหน้าตามกำหนดส่ง)
- [ ] Personal AI Memory (Gemini จำบทสนทนาเดิม per-user)
- [ ] Document/PDF Q&A (ส่ง PDF ให้ AI สรุป + ถามตอบ)
- [ ] Image OCR (อ่านโจทย์/สรุปจากรูปถ่ายกระดาน)
- [ ] Voice Message Support (ถอดเสียง → ตอบกลับ)
- [ ] Web Admin Dashboard (จัดการ users/blacklist/broadcast ผ่านเว็บ)

---

## 📝 License

MIT License — ใช้ได้อย่างอิสระ

---

## 👥 ผู้พัฒนา

พัฒนาโดยนักเรียนห้อง ม.5/2 โรงเรียนเบญจมราชูทิศ  
ผู้ใช้งานปัจจุบัน: **40+ คน** | Active User: **10 คน**  
อัปเดตล่าสุด: **26 เมษายน 2569**

## 🙏 ขอบคุณ

- **เพื่อนๆ ห้อง MTC ม.5/2** — สำหรับการใช้งานและ Feedback ที่ทำให้บอทดีขึ้นทุกวัน
- **LINE Developers** — สำหรับ Messaging API SDK
- **Google** — สำหรับ Gemini AI และ Firebase
- **Anthropic Claude & Google Gemini** — คู่หู AI Developer ประจำโปรเจกต์ 🤝

---

<div align="center">

Made with ❤️ by MTC Students

ถ้าชอบอย่าลืมกด ⭐ ให้โปรเจกต์ของเราด้วยนะ!

</div>
