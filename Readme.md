# MTC Assistant

## สรุปสั้น ๆ

MTC Assistant เป็นบอทซึ่งเขียนด้วย Python ออกแบบโครงสร้างแบบ modular (handlers, features, utils) เหมาะกับการสาธิตทักษะการออกแบบซอฟต์แวร์และการจัดการ logic ของบอทในระดับโปรเจกต์จริง
จุดประสงค์การใช้งานสำหรับห้องเรียน MTC เพื่อเป็นผู้ช่วยงานต่างๆในห้อง

---

## สารบัญ

* [Features](#features-1)
* [Tech stack](#tech-stack-1)
* [Prerequisites](#prerequisites-1)
* [ไอเดียสถานะต่อยอด](#ไอเดียสถานะต่อยอด)
* [Contributing](#contributing)
* [License](#license-1)

---

## Features

* รับคำสั่งจากผู้ใช้และตอบกลับตาม handler ที่กำหนด
* มีโครงสร้างแยก `features` ทำให้เพิ่มความสามารถใหม่ได้ง่าย
* เชื่อมกับฐานข้อมูลหรือ API ภายนอกเพื่อเก็บ/อ่านข้อมูล เช่น Gemini-API

---

## Tech stack

* Python 3.8+
* Flask
* gunicorn
* line-bot-sdk
* google-generativeai
* requests
* tzdata
* firebase-admin

---

## Prerequisites

* Python 3.8+
* Access token, Channel Secret สำหรับ Line Application

---

## ไอเดียสถานะต่อยอด

* เพิ่ม persistent storage (SQLite / Postgres)
* เพิ่ม admin commands (เช็ค log, เรียก debug info)
* ทำหน้า dashboard เบื้องต้น (Flask/FastAPI + simple UI)
* เพิ่ม NLP เบื้องต้น (เช่น intent classification) เพื่อให้บอทเข้าใจคำสั่งได้ดีขึ้น

---

## Contributing

1. Fork repository
2. สร้าง branch ใหม่: `git checkout -b feature/your-feature`
3. ทำการแก้ไข และเพิ่ม test
4. เปิด PR มาที่ repo ต้นฉบับ

---

## License

MIT License

---