<div align="center">

# 🤖 MTC Assistant

**LINE Bot ผู้ช่วยอัจฉริยะสำหรับนักเรียน**

พัฒนาโดยนักเรียนชั้น ม.4/2 โรงเรียนเบญจมราชูทิศ  
เพื่อช่วยเหลือเพื่อนๆ ในการจัดการชีวิตประจำวันในโรงเรียน

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0-000000?style=flat-square&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![LINE](https://img.shields.io/badge/LINE_Bot-00C300?style=flat-square&logo=line&logoColor=white)](https://github.com/line/line-bot-sdk-python)
[![Firebase](https://img.shields.io/badge/Firebase-FFCA28?style=flat-square&logo=firebase&logoColor=black)](https://firebase.google.com/)

![Version](https://img.shields.io/badge/version-21.0-blue?style=flat-square)
![Status](https://img.shields.io/badge/status-active-success?style=flat-square)
![Users](https://img.shields.io/badge/users-40+-orange?style=flat-square)

---

</div>

## 💭 เรื่องราว

เริ่มจากความต้องการมี **Personal Assistant** ที่เข้าใจชีวิตนักเรียนจริงๆ ไม่ใช่แค่บอทตอบคำถาม แต่เป็นเพื่อนที่คอยช่วยเหลือตลอด 24 ชั่วโมง

ตอนนี้มีเพื่อนๆ กว่า **40 คน** ใช้งานอยู่จริง ✨

## 🎯 ความสามารถ

### 📚 เรื่องเรียน
- **เช็คตารางเรียน** - ดูว่าเรียนอะไรต่อไป อยู่ห้องไหน
- **นับถอยหลังสอบ** - บอกเหลืออีกกี่วันก่อนสอบกลาง/ปลายภาค
- **จัดการการบ้าน** - เพิ่ม/ดู/ลบการบ้านได้ง่ายๆ
- **เฉลยวิชาต่างๆ** - ลิงก์เฉลยชีวะ ฟิสิกส์ ครบครัน

### ⏰ จัดการเวลา
- **คาบต่อไป** - บอกว่าจะเรียนอะไร เหลือเวลาอีกกี่นาที
- **คำนวณเวลา** - แสดงเวลาที่เหลือจนถึงคาบถัดไป
- **ตารางแบบเรียลไทม์** - อัพเดททุกวัน ตามตารางจริงของห้อง

### 🤖 AI ฉลาดๆ
- **ตอบคำถาม** - ใช้ Gemini AI ตอบได้เกือบทุกเรื่อง
- **ค้นหาเพลง** - หาเพลงใน YouTube ให้
- **แนะนำอาหาร** - สุ่มเมนูให้ตามงบประมาณ (อยู่ในโค้ดแล้ว พร้อมเปิดใช้!)

### 👨‍💼 สำหรับ Admin
- **ประกาศ** - ส่งข้อความถึงทุกคนในห้อง
- **จัดการผู้ใช้** - แบนคนที่ spam ได้
- **ดูสถิติ** - เช็คยอดผู้ใช้ ข้อความ

## 🎮 วิธีใช้งาน

### คำสั่งพื้นฐาน
```
งาน                    → ดูใบงาน
ตารางเรียน             → ดูตารางสอน
คาบต่อไป               → ดูว่าเรียนอะไรต่อ
สอบ                    → นับถอยหลังวันสอบ
การบ้าน                → ดูการบ้านทั้งหมด
ลิงก์                  → เมนูลิงก์สำคัญ (Flex Message)
คำสั่ง                 → ดูคำสั่งทั้งหมด
```

### จัดการการบ้าน
```
สั่งการบ้าน | ฟิสิกส์ | ทำแบบฝึกหัด 4.1 | วันศุกร์
```

### ถาม AI
```
อธิบายทฤษฎีสัมพัทธภาพให้หน่อย
แนะนำวิธีจำสูตรคณิตศาสตร์
```

### คำสั่ง Admin (เฉพาะผู้ดูแล)
```
ประกาศ [ข้อความ]             → ส่งประกาศถึงทุกคน
แบน [user_id] [เหตุผล]       → แบนผู้ใช้
ปลดแบน [user_id]             → ปลดแบน
รายชื่อแบน                   → ดูคนที่ถูกแบน
admin                        → ดูคำสั่งแอดมิน
```

## 🛠️ เทคโนโลยี

- **Python 3.8+** - ภาษาหลัก
- **Flask** - Web framework
- **LINE Bot SDK** - สำหรับทำบอท
- **Firebase Firestore** - ฐานข้อมูล
- **Gemini AI** - ระบบ AI ตอบคำถาม
- **Render** - Deploy และ hosting

## 📁 โครงสร้างโค้ด

```
mtc-assistant/
├── main.py              # Flask app และ initialization
├── config.py            # Configuration และ constants
├── features.py          # ฟีเจอร์ต่างๆ (ตารางเรียน, AI, ฯลฯ)
├── handlers.py          # จัดการ events จาก LINE
├── broadcast.py         # ระบบประกาศ
├── user_blacklist.py    # ระบบแบนผู้ใช้
├── requirements.txt     # Python packages
└── firebase_key.json    # Firebase credentials
```

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
export GEMINI_API_KEY="your_gemini_api_key"
export ADMIN_USER_IDS="your_line_user_id"
```

### 4. ใส่ Firebase Credentials
วาง `firebase_key.json` ไว้ใน root directory

### 5. รันโปรเจกต์
```bash
python main.py
```

Bot จะรันที่ `http://localhost:5001`

## 📊 Endpoints

- `GET /` - Health check และ status
- `POST /callback` - LINE webhook endpoint
- `GET /healthz` - Detailed health check (JSON)
- `GET /metrics` - Performance metrics
- `GET /stats` - Bot statistics

## 🎓 สิ่งที่เรียนรู้จากโปรเจกต์

### Technical Skills
- RESTful API design
- Webhook handling
- Database management (Firebase)
- Error handling และ logging
- Rate limiting
- Performance monitoring

### Soft Skills
- การแก้ปัญหา (Debugging)
- การออกแบบระบบ (Architecture)
- การทำงานเป็นทีม
- การบริหารโปรเจกต์

## 🐛 Known Issues

- ~~Gemini model name อาจต้องเปลี่ยนเป็น `gemini-1.5-flash`~~ (กำลังตรวจสอบ)
- ~~Missing `datetime` import in broadcast.py~~ (แก้แล้วใน branch hotfix)

## 📈 Roadmap

- [x] ระบบตารางเรียน
- [x] ระบบการบ้าน (Firebase)
- [x] AI integration (Gemini)
- [x] Broadcast system
- [x] Rate limiting
- [x] User blacklist
- [ ] ระบบแนะนำอาหาร (โค้ดพร้อมแล้ว!)
- [ ] คำนวณเกรดและ GPA (โค้ดพร้อมแล้ว!)
- [ ] ระบบ Quick Notes
- [ ] Expense Tracker
- [ ] Study Timer (Pomodoro)

## 🤝 Contributing

ยินดีรับ Pull Request! ถ้าอยากช่วยพัฒนาบอท:

1. Fork โปรเจกต์
2. สร้าง feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. เปิด Pull Request

## 📝 License

MIT License - ใช้ได้อย่างอิสระ

## 👥 ผู้พัฒนา

พัฒนาโดยนักเรียนห้อง **ม.4/2** โรงเรียนเบญจมราชูทิศ

**ผู้ใช้งานปัจจุบัน:** 40+ คน  
**อัพเดทล่าสุด:** กุมภาพันธ์ 2569

## 🙏 ขอบคุณ

- **เพื่อนๆ ห้อง MTC ม.4/2** - ที่ใช้งานและให้ feedback
- **คณะครู** - ที่สนับสนุนโปรเจกต์
- **LINE Developers** - สำหรับ Bot SDK
- **Google** - สำหรับ Gemini AI และ Firebase
- **Anthropic Claude** - ช่วยดีบัก code 😊

## 📞 ติดต่อ

พบปัญหาหรือมีข้อเสนอแนะ? เปิด [Issue](https://github.com/yourusername/mtc-assistant/issues) ได้เลย!

---

<div align="center">

**Made with ❤️ by MTC Students**

ถ้าชอบอย่าลืมกด ⭐ ด้วยนะ!

</div>
