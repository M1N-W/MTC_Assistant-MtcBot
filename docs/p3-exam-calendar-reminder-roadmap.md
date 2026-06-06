# P3 Exam Calendar & Reminder System Roadmap

## 1. ภาพรวม

P3 คือแผนพัฒนาระบบปฏิทินสอบและกิจกรรมสำหรับ MTC Assistant เพื่อให้ผู้ดูแลสร้างรายการสอบหรือกิจกรรมตามห้องและภาคเรียน นักเรียนดูรายการที่กำลังจะมาถึงผ่าน LINE และระบบส่งการแจ้งเตือนที่ตรวจสอบย้อนหลังได้โดยไม่ส่งซ้ำ

P3 เป็นงานหลังช่วง freeze และไม่อยู่ใน critical path ของวันที่ 9 มิถุนายน 2026 งานก่อนวันดังกล่าวควรเน้นความเสถียรของระบบที่ deploy และทดสอบแล้ว ไม่ควรเริ่ม Firestore schema ใหม่ งาน scheduler หรือ AI broadcast ในช่วง final polish

ระบบ AI ใน P3 มีหน้าที่สร้าง draft เท่านั้น เนื้อหาที่ AI สร้างต้องผ่านการตรวจ แก้ไข และอนุมัติโดยผู้ดูแลก่อนส่งให้นักเรียน

## 2. บริบทระบบปัจจุบัน

- LINE webhook ใช้ `command_router.py` สำหรับคำสั่งนักเรียน
- คำสั่ง `ปฏิทินกิจกรรม` และ `ปฏิทิน` ยัง route ไปยัง exam countdown ปัจจุบัน
- คำสั่ง `สอบ`, `วันสอบ`, `กลางภาค` และ `ปลายภาค` ใช้ exam countdown เดียวกัน
- exam countdown ปัจจุบันอ่านวันที่จาก config แบบ hardcoded และยังไม่ class-aware
- Dashboard General Links Editor MVP มีเส้นทาง Browser -> Next.js proxy -> Flask admin API -> Firestore ที่ใช้งานแล้ว
- โครงสร้างข้อมูลใหม่ของระบบใช้ class/term scope เช่น `classes/{classId}/terms/{termId}/...`
- ระบบมี broadcast/admin tooling และประวัติการส่งแบบ root-level อยู่แล้ว แต่ยังไม่ใช่ reminder pipeline ที่ class-aware และ idempotent
- ระบบมี Gemini API integration อยู่แล้ว แต่ยังไม่มี approval workflow สำหรับ study summary
- timetable และ general links รองรับพฤติกรรม class-aware สำหรับ MTC12/MTC13 บางส่วนแล้ว ขณะที่ exam countdown ยังเป็นข้อจำกัดที่ต้องแก้ใน P3
- Rich Menu ปัจจุบันมีหกรายการ: `ตารางเรียน`, `เช็คเวลาเรียน`, `บันทึกการบ้าน`, `ลิงก์ที่สำคัญ`, `การบ้าน` และ `ช่วยเหลือ`
- Rich Menu ปัจจุบันไม่มี `ปฏิทินกิจกรรม`
- P3 ต้องเปิดทางให้คำสั่งและ dashboard รองรับ `ปฏิทินกิจกรรม` / `ปฏิทินสอบ` ในอนาคต แต่ไม่บังคับให้นำ `ปฏิทินกิจกรรม` กลับเข้า Rich Menu ทันที

## 3. เป้าหมายผลิตภัณฑ์

- นักเรียนดูการสอบและกิจกรรมที่กำลังจะมาถึงได้จาก LINE
- ผู้ดูแลสร้าง แก้ไข ยกเลิก และจัดการ event ได้โดยไม่ต้องแก้โค้ดหรือ deploy bot
- ทุก event และ reminder ผูกกับ `class_id` และ `term_id`
- รายการใน LINE เรียงตามวันและบอกจำนวนวันที่เหลืออย่างอ่านง่าย
- reminder broadcast มี idempotency key/state และไม่ส่งรายการเดิมซ้ำ
- ผู้ดูแลเห็น dry-run และขอบเขตผู้รับก่อนส่งจริง
- AI ช่วยร่างสรุปอ่านสอบจากหัวข้อที่ผู้ดูแลยืนยัน โดยไม่ข้าม human review
- ระบบเก็บ audit trail ที่ตอบได้ว่าใครสร้าง แก้ อนุมัติ และส่งข้อมูลเมื่อใด

## 4. สิ่งที่ยังไม่ทำ

- ไม่สร้าง calendar app เต็มรูปแบบ
- ไม่สร้าง LIFF calendar UI
- ไม่เปิดให้นักเรียนสร้างหรือแก้ event
- ไม่ส่ง AI-generated summary ที่ยังไม่ผ่านการตรวจ
- ไม่ให้ AI สร้างเนื้อหาอ่านสอบจากการคาดเดาหรือ hallucination
- ไม่ broadcast ข้ามทุกห้องโดยปริยาย
- ไม่เปลี่ยน Rich Menu ทันที
- ไม่แทนที่ Learning Resources Phase B/C
- ไม่ผูก P3 กับการทำ Learning Resources apply mode
- ไม่สร้าง class-admin role system เต็มรูปแบบก่อน dashboard auth พร้อม
- ไม่เปลี่ยน MTC67 หรือเปิดเผย MTC67 ใน UI
- ไม่เริ่มจาก AI image generation

## 5. Firestore Schema ที่เสนอ

เส้นทางหลัก:

```text
classes/{classId}/terms/{termId}/exam_events/{eventId}
```

ตัวอย่าง document:

```json
{
  "id": "physics-midterm-2026-07-15",
  "class_id": "mtc13",
  "term_id": "2569-t1",
  "title": "สอบกลางภาคฟิสิกส์",
  "subject_id": "physics",
  "subject_label": "ฟิสิกส์",
  "exam_type": "midterm",
  "exam_date": "2026-07-15",
  "start_time": "09:00",
  "end_time": "10:30",
  "location": "ห้อง 521",
  "topics": ["การเคลื่อนที่", "แรงและกฎของนิวตัน"],
  "note": "นำเครื่องคิดเลขตามระเบียบห้องสอบ",
  "source_note": "ยืนยันจากตารางสอบฉบับวันที่ 2026-07-01",
  "status": "active",
  "reminder_offsets_days": [1],
  "reminder_state": {},
  "ai_summary_status": "not_requested",
  "ai_summary_draft": null,
  "ai_summary_approved": null,
  "summary_image_url": null,
  "created_at": "server timestamp",
  "updated_at": "server timestamp",
  "created_by": "admin account id",
  "updated_by": "admin account id"
}
```

ข้อกำหนดของ field:

- `id`: stable document ID ที่ผ่าน validation และตรงกับ `eventId`
- `class_id`, `term_id`: ต้องตรงกับ path และห้ามรับค่าโดยเชื่อ client โดยตรง
- `title`: ชื่อที่นักเรียนเข้าใจได้และไม่ว่าง
- `subject_id`: canonical subject ID จาก allowlist
- `subject_label`: ชื่อแสดงผลภาษาไทย
- `exam_type`: เช่น `midterm`, `final`, `quiz`, `activity`, `other`
- `exam_date`: วันที่ตามรูปแบบ `YYYY-MM-DD` ใน timezone `Asia/Bangkok`
- `start_time`, `end_time`, `location`: optional
- `topics`: array ของหัวข้อสั้นที่ผู้ดูแลตรวจแล้ว
- `note`, `source_note`: optional โดย `source_note` ใช้ระบุที่มาหรือเวอร์ชันประกาศ
- `status`: `draft`, `active`, `cancelled` และอาจเพิ่ม `completed` ภายหลัง
- `reminder_offsets_days`: จำนวนวันก่อน event ที่อนุญาต เช่น `[1]`
- `reminder_state`: map แยกตาม offset เก็บสถานะ, idempotency key, เวลา, ผู้สั่ง และผลการส่ง
- `ai_summary_status`: `not_requested`, `draft`, `in_review`, `approved`, `rejected`
- `ai_summary_draft`: structured draft ที่ยังส่งไม่ได้
- `ai_summary_approved`: snapshot ของเนื้อหาที่ผู้ดูแลอนุมัติ
- `summary_image_url`: URL ของภาพที่ render จาก approved content แล้ว
- `created_at`, `updated_at`: server timestamp
- `created_by`, `updated_by`: admin identity ที่ตรวจสอบสิทธิ์แล้ว

ห้ามเก็บ:

- secrets, API keys, session tokens หรือ dashboard tokens
- raw LINE user IDs นอกกรณีที่เป็นส่วนของ user model เดิมและมีเหตุผลด้าน audit ชัดเจน
- ข้อมูลส่วนตัวของนักเรียน
- รายชื่อหรือคะแนนรายบุคคล
- เนื้อหาหนังสือเรียนที่มีลิขสิทธิ์แบบคัดลอกยาวเข้า summary
- prompt หรือ output ที่มีข้อมูลลับ

## 6. Event Lifecycle

สถานะหลัก:

- `draft`: ผู้ดูแลกำลังกรอกหรือยังไม่ยืนยัน นักเรียนมองไม่เห็น และ reminder ใช้งานไม่ได้
- `active`: ผ่านการตรวจ event แล้ว แสดงใน LINE และเข้ากระบวนการ reminder ได้
- `cancelled`: ยกเลิกแล้ว ไม่ส่ง reminder ใหม่ แต่เก็บประวัติไว้
- `completed`: optional สำหรับ event ที่ผ่านไปแล้ว หากยังไม่เพิ่มสถานะนี้ให้ query จากวันที่แทน

ลำดับการทำงาน:

```text
สร้าง event
-> ตรวจ title/date/scope/topics
-> activate
-> ขอ AI draft ได้แบบ optional
-> ผู้ดูแลตรวจและแก้ draft
-> อนุมัติ summary
-> dry-run reminder
-> ส่ง reminder ตาม idempotency gate
-> event ผ่านวันสอบและคงเป็นประวัติแบบ read-only
```

การแก้วันสอบหรือยกเลิกหลังส่ง reminder ต้องสร้าง audit event และทำให้ reminder plan เดิมหมดอายุ ห้ามลบประวัติการส่งเพื่อทำให้ระบบดูเหมือนไม่เคยส่ง

## 7. P3A: Event Model และ Validator

P3A ควรเป็น delta ที่เล็กที่สุดก่อนมี dashboard หรือ write workflow:

- สร้าง model/schema normalization แยกจาก Firestore I/O
- ใช้ pure validator functions ที่ input เดิมให้ output เดิมและไม่มี side effect
- parse `exam_date` แบบ strict `YYYY-MM-DD` และตรวจวันที่จริง
- parse เวลาแบบ strict `HH:MM` และตรวจ `start_time < end_time` เมื่อมีทั้งคู่
- normalize `topics` เป็น string array ที่ trim แล้ว จำกัดจำนวนและความยาว
- ใช้ allowlist สำหรับ `subject_id` และ `exam_type`
- validate `class_id`, `term_id`, `event_id` ไม่ให้มี slash หรือ path traversal
- ตรวจว่า IDs ใน payload ตรงกับ path parameters
- reject unknown fields หรือกำหนด normalization policy อย่างชัดเจน
- แยก validation error เป็น field-level structured errors
- ไม่มี production Firestore writes ใน unit tests
- ใช้ fake Firestore สำหรับ repository/service tests

Exit criteria:

- valid event normalize ได้ deterministic
- invalid date, time, scope, subject และ status ถูก reject
- ไม่มี network access ใน validator tests
- test suite เดิมผ่าน
- rollback คือไม่เชื่อม validator เข้ากับ runtime route จนกว่า API contract ผ่าน review

## 8. P3B: Dashboard Exam Events Editor MVP

MVP:

- list events ตาม class/term
- filter สถานะและช่วงวันที่แบบ bounded query
- create event
- edit event
- cancel event โดยไม่ hard delete
- fields ขั้นต่ำ: subject, title, exam date, topics, note
- preview ข้อมูลที่จะปรากฏใน LINE
- ไม่มี AI generation ใน dashboard MVP แรก
- ไม่มี dashboard redesign ขนาดใหญ่

ขอบเขตสถาปัตยกรรม:

```text
Browser
-> Next.js /api/admin/* proxy
-> Flask /api/admin/classes/{classId}/terms/{termId}/exam-events
-> validator/service
-> Firestore
```

- browser ต้องไม่ได้รับ `MTC_DASHBOARD_API_TOKEN`
- Flask ต้องตรวจ auth, role, `class_id` และ `term_id` ทุก request
- frontend hiding ไม่ถือเป็น authorization
- writes ต้องบันทึก `created_by` / `updated_by`
- query ต้อง paginate หรือ bound จำนวนรายการ
- webhook `/callback` ต้องไม่ขึ้นกับ dashboard

แนวทาง UI สามแบบ:

1. Classroom OS Table: ตารางหนาแน่น อ่านเร็ว ใช้ `#12372A`, accent `#F4B942`, surface `#FFF8E7`, row transition `0.18s ease-out`
2. Calendar Board: แบ่งรายสัปดาห์ ใช้ `#0F172A`, accent `#38BDF8`, warning `#F97316`, panel transition `0.24s cubic-bezier(0.22, 1, 0.36, 1)`
3. Timeline Review: timeline เน้น approval ใช้ `#1D4ED8`, support `#16A34A`, danger `#DC2626`, state transition `0.2s ease-out`

คำแนะนำ: ใช้ Classroom OS Table เพราะเข้ากับ dashboard เดิม ตรวจข้อมูลหลายรายการได้เร็ว และมี blast radius ต่ำที่สุด

P3B ยังไม่ต้องมี visual asset ใหม่ หากเพิ่ม icon ให้ใช้ icon library เดิมที่ขนาด 16-20 px และไม่เพิ่ม sprite sheet หรือ atlas

## 9. P3C: คำสั่ง LINE สำหรับปฏิทินสอบ

คำสั่งที่ควรรองรับโดยรักษาความหมายเดิม:

- `สอบ`
- `ปฏิทินสอบ`
- `ปฏิทินกิจกรรม`
- `ปฏิทิน`
- `กลางภาค`
- `ปลายภาค`

พฤติกรรม:

- resolve `ClassContext` และ active term ก่อน query
- อ่านเฉพาะ `active` events ของ class/term นั้น
- เรียง `exam_date`, `start_time`, `title`
- แสดงจำนวนวันที่เหลือใน timezone `Asia/Bangkok`
- แสดง subject/title และ topics แบบสั้น
- แยกกลางภาค/ปลายภาคด้วย `exam_type` ไม่ใช้ substring อย่างเดียว
- จำกัดจำนวนรายการต่อข้อความและมีข้อความบอกเมื่อยังมีรายการเพิ่มเติม
- empty state ต้องบอกว่าไม่มีรายการที่ประกาศ และแนะนำให้ตรวจใหม่ภายหลัง
- Firestore unavailable ต้อง fail safely โดยไม่รั่ว internal error
- MTC12 และ MTC13 ต้องไม่เห็น event ข้ามห้องหรือข้าม term

การเปลี่ยน route ต้องทำใน P3C พร้อม focused routing tests ไม่ควรเปลี่ยน command matching ระหว่าง P3A/P3B

## 10. P3D: Reminder Broadcast System

ค่าเริ่มต้นคือเตือนหนึ่งวันก่อนสอบผ่าน `reminder_offsets_days: [1]` ส่วน same-day reminder ให้เป็น feature ภายหลังเมื่อมีนโยบายชัดเจน

ข้อกำหนด:

- recipients ต้อง resolve จาก class/term scope ที่ถูกต้อง
- dry-run เป็นค่าเริ่มต้น แสดง event, offset, recipient count และข้อความโดยไม่ส่ง
- apply/trigger ต้องเป็นคำสั่ง explicit และมีสิทธิ์
- scheduler ภายหลังต้องใช้ logic เดียวกับ manual trigger
- idempotency key ควรรวม `class_id`, `term_id`, `event_id`, `offset_days` และ event revision
- transaction หรือ atomic claim ต้องเกิดก่อนส่ง เพื่อลดการส่งซ้ำจาก concurrent workers
- `reminder_state` ต้องเก็บ planned/claimed/sent/failed พร้อม timestamp และ result
- retry ต้องไม่สร้างการส่งซ้ำแบบไม่ทราบผล หาก LINE ตอบไม่ชัดเจนให้ mark สถานะเพื่อ manual review
- ทุก run มี audit log
- ห้ามใช้ global `get_all_users()` สำหรับ class-scoped reminder

ตัวอย่างข้อความ:

```text
เตือนสอบพรุ่งนี้

ฟิสิกส์: สอบกลางภาค
เวลา 09:00-10:30 น.
หัวข้อ: การเคลื่อนที่, แรงและกฎของนิวตัน

ตรวจอุปกรณ์และทบทวนหัวข้อที่ประกาศไว้ให้พร้อม
```

## 11. P3E: AI Study Summary Draft

- AI รับเฉพาะ event ที่ active และ topics ที่ผู้ดูแลยืนยัน
- prompt ต้องสั่งไม่ให้เติมรายละเอียดที่ไม่มี source รองรับ
- output ควรเป็น structured JSON/text เช่น title, key_points, checklist, cautions และ source_gaps
- หากข้อมูลไม่พอ AI ต้องระบุช่องว่าง ไม่เดาคำตอบ
- draft เริ่มที่ `ai_summary_status: draft`
- ผู้ดูแลตรวจ แก้ และเปลี่ยนเป็น `approved`
- เก็บ approved snapshot แยกจาก draft เพื่อ audit
- การแก้ topics หลัง approval ต้องทำให้ approval เดิมหมดอายุ
- ไม่มี automatic broadcast จาก AI generation endpoint
- ไม่มี unreviewed AI-generated summaries ใด ๆ ที่สามารถ broadcast ให้นักเรียนได้

## 12. P3F: การ Render ภาพสรุป

ห้ามสั่ง AI ให้สร้างภาพที่มีข้อความภาษาไทยสำหรับ broadcast โดยตรง เพราะควบคุมการสะกด layout และความถูกต้องได้ยาก

pipeline ที่ปลอดภัย:

```text
exam event + topics
-> AI structured draft
-> human review/edit
-> approved structured content
-> deterministic template render
-> approved image attachment
-> broadcast
```

ตัว render อาจใช้ PNG, SVG หรือ HTML-to-image ในภายหลัง แต่ต้อง deterministic จาก approved content เท่านั้น ขนาดเริ่มต้นที่เหมาะกับ LINE คือ 1080 x 1350 px พร้อม safe area 72 px สีพื้น `#F8FAFC`, ตัวอักษร `#0F172A`, accent `#0F766E`, warning `#B45309` และไม่มี animation

ภาพต้องเก็บใน hosting/storage ที่ควบคุมสิทธิ์และ lifecycle ได้ URL ต้องใช้ HTTPS และ broadcast แนบเฉพาะ `summary_image_url` ที่ผูกกับ approved revision เดียวกัน หากเนื้อหาถูกแก้ต้อง render และอนุมัติภาพใหม่

## 13. ความเสี่ยงด้าน Security และ Privacy

- Duplicate reminders: worker ซ้อนหรือ retry อาจส่งซ้ำ ต้องมี atomic claim และ idempotency state
- Wrong-class broadcast: การใช้ global user list จะส่งผิดห้อง ต้อง query ผู้รับตาม class scope
- Cross-class leakage: path หรือ cache key ที่ไม่มี class/term อาจคืนข้อมูลข้ามห้อง
- AI hallucination: สรุปอาจเพิ่มรายละเอียดที่ไม่อยู่ใน topics/source ต้องมี structured gaps และ human review
- Copyright: ห้ามคัดลอกหนังสือเรียนหรือเฉลยยาวเข้า summary
- Missing approval: endpoint ส่งต้องตรวจ approved revision ฝั่ง backend เสมอ
- Token leakage: browser, logs, docs และ Firestore ห้ามมี Gemini/LINE/dashboard tokens
- Weak dashboard scope: frontend-only guards ไม่พอ ต้อง enforce ใน Flask API
- Student privacy: event และ summary ห้ามมีคะแนน รายชื่อ หรือข้อมูลสุขภาพรายบุคคล
- Broadcast abuse: ต้องจำกัด role, rate, audience และเก็บ audit
- Deploy-freeze risk: ไม่เริ่ม runtime implementation ก่อนพ้น June 9 freeze

Architecture smell ปัจจุบัน: exam countdown ยังอ่าน hardcoded config และ broadcast helper ยังเน้น root-level/global audience จึงไม่ควรนำมาใช้กับ P3 โดยตรงโดยไม่เพิ่ม class-aware boundary

## 14. Test Plan

- validator รับ valid schema และคืน normalized event
- validator reject invalid date/time/IDs/subject/status/unknown fields
- schema normalization เป็น deterministic และไม่ mutate input
- dashboard API reject unauthenticated request
- dashboard API reject role หรือ class/term ที่ไม่มีสิทธิ์
- create/edit/cancel เก็บ audit fields ถูกต้อง
- LINE commands เรียง event และคำนวณ days remaining ถูกต้อง
- LINE empty state และ Firestore unavailable state ปลอดภัย
- filter `กลางภาค` / `ปลายภาค` ใช้ `exam_type` ถูกต้อง
- MTC12/MTC13 และ term ต่างกันไม่รั่วข้อมูลหากัน
- reminder dry-run ไม่มี LINE push
- reminder apply ส่งครั้งเดียวต่อ idempotency key
- concurrent claim ป้องกัน duplicate
- failed/unknown delivery state ไม่ถูก retry แบบ blind
- AI draft endpoint ไม่ broadcast
- broadcast gate reject draft/in-review/rejected summary
- approved content revision ต้องตรงกับ image revision
- image attachment ใช้ได้หลัง approval เท่านั้น
- MTC67 exact-match regression ยังคงผ่านเมื่อ P3C แตะ routing

Performance budget:

- LINE event query เป็น bounded query และไม่ stream ทั้ง collection
- dashboard list paginate
- reminder recipient query จำกัดเฉพาะ class และไม่ scan global users
- AI/render ไม่ทำงานใน LINE webhook request path

## 15. Manual Test Plan

1. สร้าง draft event ผ่าน dashboard ด้วย test class/term
2. ตรวจว่า draft ยังไม่ปรากฏใน LINE
3. activate event และเรียก `ปฏิทินสอบ`
4. ตรวจลำดับวันที่ จำนวนวันที่เหลือ topics และ empty state
5. ยืนยันว่า MTC13 เห็นเฉพาะ event ของ MTC13
6. ยืนยันว่า MTC12 ไม่เปลี่ยนและไม่เห็น event ของ MTC13
7. รัน reminder dry-run และตรวจ event, audience, message โดยไม่มี push
8. trigger ไปยัง test user/channel ก่อน และตรวจ audit/reminder state
9. trigger ซ้ำด้วย idempotency key เดิมและยืนยันว่าไม่ส่งซ้ำ
10. สร้าง AI summary draft และยืนยันว่าไม่สามารถส่งได้
11. แก้และอนุมัติ summary
12. render ภาพจาก approved content
13. ทดสอบ image attachment กับ test user/channel ก่อน broad class broadcast
14. ตรวจว่า cancellation หรือ date revision ทำให้ reminder plan/approval เก่าหมดอายุอย่างถูกต้อง

## 16. ลำดับ Implementation ที่แนะนำ

- P3A: planning, schema, pure validator และ repository contract
- P3B: dashboard exam events editor MVP ไม่มี AI
- P3C: LINE read-only calendar แบบ class/term scoped
- P3D: reminder planner และ dry-run เท่านั้น
- P3E: controlled reminder apply/manual trigger แล้วจึงพิจารณา scheduler
- P3F: AI study-summary draft พร้อม human review/approval gate
- P3G: deterministic template-rendered summary image
- P3H: optional Help Flex/Rich Menu integration หลัง usage และ product decision ชัดเจน

แต่ละ phase ควรเป็น commit แยก มี tests และ manual-test record ตาม blast radius ไม่รวม dashboard, routing, scheduler และ AI ไว้ใน batch เดียว

## 17. Stop Conditions

หยุดก่อนแก้หรือส่งต่อทันทีเมื่อ:

- working tree dirty นอก scope
- `main` หรือ `origin/main` เคลื่อนจาก checkpoint ที่คาดโดยยังไม่ได้ review
- มี production Firestore writes ก่อน dry-run และ validation
- scheduler สามารถ broadcast โดยไม่มี dry-run/approval policy
- AI summary สามารถส่งได้โดยไม่มี admin approval
- implementation แตะ MTC67 หรือทำให้ MTC67 ปรากฏใน help/menu/docs
- ต้อง commit secrets, tokens หรือ credentials
- ต้องเปลี่ยน Rich Menu ก่อนมี explicit decision
- class/term authorization ยังไม่ enforce ฝั่ง backend
- recipient query ยังเป็น global audience
- ไม่สามารถพิสูจน์ idempotency ภายใต้ concurrent trigger

Rollback plan:

- ปิด feature flag สำหรับ LINE read path หรือ reminder apply
- คง event documents ไว้และเปลี่ยนเป็น `cancelled` แทน delete
- ปิด scheduler ก่อน rollback runtime
- เก็บ reminder/audit history ไว้ตรวจสอบ
- กลับไปใช้ exam countdown เดิมชั่วคราวจนกว่า P3C ผ่าน verification

## 18. Prompt สำหรับ Codex ในอนาคต

### P3A

> Implement P3A exam event schema normalization and pure validators only. Do not add Firestore writes, dashboard UI, routing, broadcasts, AI, or deploy changes. Add focused unit tests for dates, IDs, scope, subjects, status, and input immutability.

### P3B

> Implement the P3B dashboard exam events editor MVP using the existing Next.js proxy and Flask admin API boundary. Support list/create/edit/cancel for one authorized class/term. Do not add AI, reminders, Rich Menu changes, or broad dashboard redesign.

### P3C

> Implement P3C read-only LINE exam calendar commands backed by class/term-scoped active events. Preserve existing triggers, add `ปฏิทินสอบ`, prevent cross-class leakage, keep safe empty/error states, and do not change MTC67 or Rich Menu.

### P3D

> Implement P3D reminder planning in dry-run mode only. Produce deterministic class-scoped plans and idempotency keys without LINE push or scheduler activation. Add duplicate-prevention and concurrency-focused tests.

## 19. คำถามที่ต้องตัดสินใจก่อน implementation

- subject allowlist เริ่มต้นมีวิชาใดบ้าง และใครเป็นเจ้าของ taxonomy
- ใครมีสิทธิ์สร้าง แก้ activate และ cancel event
- ทุก event ต้องมีผู้อนุมัติก่อน active หรือไม่
- reminder เริ่มต้นคือหนึ่งวันก่อนเสมอหรือกำหนดต่อ event
- same-day reminder จำเป็นหรือสร้าง notification fatigue
- broadcast audience คือ active class users ทั้งหมดหรือรองรับกลุ่มย่อย
- ต้องให้ admin ยืนยัน audience ทุกครั้งก่อน apply หรือไม่
- scheduler จะอยู่ใน Render worker, cron job หรือบริการอื่น
- summary image ควรเก็บใน Firebase Storage, Firebase Hosting หรือ storage อื่น
- approved summary และภาพควรเก็บ retention นานเท่าใด
- Rich Menu ควรนำ `ปฏิทินกิจกรรม` กลับมาเมื่อใด หรือใช้ Help Flex/คำสั่งต่อไป

## 20. ข้อเสนอแนะ

เริ่มหลังวันที่ 9 มิถุนายน 2026 ด้วย P3A schema/validator แล้วทำ P3B dashboard editor เพื่อสร้าง source of truth ที่ผู้ดูแลจัดการได้ก่อน จากนั้นจึงต่อ P3C LINE read path และ P3D reminder dry-run

อย่าเริ่มด้วย AI image generation เพราะยังไม่มี event source of truth, approval workflow, class-scoped reminder gate และ deterministic content pipeline ที่จำเป็นต่อความถูกต้องและความปลอดภัย
