import datetime
import unittest

from mtc_assistant.class_context import ClassContext
from mtc_assistant.config import LOCAL_TZ
from mtc_assistant.timetable_service import (
    build_timetable_config,
    format_timetable_status,
    get_timetable_image_message,
    get_timetable_image_url,
    get_timetable_status_text,
    normalize_timetable_config,
)


SAMPLE_SCHEDULE = {
    0: [
        {"start": "08:30", "end": "09:25", "subject": "ฟิสิกส์", "room": "331"},
        {"start": "10:20", "end": "11:15", "subject": "คณิต", "room": "632"},
        {"start": "11:15", "end": "12:10", "subject": "อังกฤษ", "room": "-"},
    ],
}


class FakeDocSnapshot:
    def __init__(self, exists, data=None):
        self.exists = exists
        self._data = data or {}

    def to_dict(self):
        return dict(self._data)


class FakeDocRef:
    def __init__(self, db, path):
        self.db = db
        self.path = path

    def get(self):
        if self.path in self.db.store:
            return FakeDocSnapshot(True, self.db.store[self.path])
        return FakeDocSnapshot(False)

    def collection(self, name):
        return FakeCollection(self.db, f"{self.path}/{name}")


class FakeCollection:
    def __init__(self, db, path):
        self.db = db
        self.path = path

    def document(self, doc_id):
        return FakeDocRef(self.db, f"{self.path}/{doc_id}")


class FakeDb:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        return FakeCollection(self, name)


def monday(hour, minute):
    return datetime.datetime(2026, 6, 1, hour, minute, tzinfo=LOCAL_TZ)


class TimetableServiceTest(unittest.TestCase):
    def test_during_class_includes_current_next_and_minutes_left(self):
        text = format_timetable_status(SAMPLE_SCHEDULE, monday(8, 40))

        self.assertIn("ตอนนี้กำลังเรียน", text)
        self.assertIn("ฟิสิกส์", text)
        self.assertIn("ห้อง 331", text)
        self.assertIn("08:30 - 09:25", text)
        self.assertIn("เหลืออีก 45 นาที", text)
        self.assertIn("คาบถัดไป", text)
        self.assertIn("คณิต", text)

    def test_during_final_class_says_last_class(self):
        text = format_timetable_status(SAMPLE_SCHEDULE, monday(11, 30))

        self.assertIn("ตอนนี้กำลังเรียน", text)
        self.assertIn("อังกฤษ", text)
        self.assertIn("ห้อง -", text)
        self.assertIn("คาบนี้เป็นคาบสุดท้ายของวันนี้", text)

    def test_between_classes_shows_next_class(self):
        text = format_timetable_status(SAMPLE_SCHEDULE, monday(9, 40))

        self.assertIn("ตอนนี้ไม่มีคาบเรียนในตาราง", text)
        self.assertIn("อีก 40 นาทีถึงคาบถัดไป", text)
        self.assertIn("คาบถัดไป", text)
        self.assertIn("คณิต", text)

    def test_before_first_class_shows_first_class(self):
        text = format_timetable_status(SAMPLE_SCHEDULE, monday(8, 0))

        self.assertIn("ยังไม่เริ่มคาบแรก", text)
        self.assertIn("อีก 30 นาทีถึงคาบแรก", text)
        self.assertIn("คาบแรก", text)
        self.assertIn("ฟิสิกส์", text)

    def test_after_final_class_shows_last_class(self):
        text = format_timetable_status(SAMPLE_SCHEDULE, monday(13, 0))

        self.assertIn("วันนี้หมดคาบเรียนแล้ว", text)
        self.assertIn("คาบสุดท้ายคือ", text)
        self.assertIn("อังกฤษ", text)

    def test_no_schedule_day_is_safe(self):
        text = format_timetable_status(SAMPLE_SCHEDULE, datetime.datetime(2026, 6, 7, 9, 0, tzinfo=LOCAL_TZ))

        self.assertEqual("วันนี้ไม่มีคาบเรียนในตาราง", text)

    def test_firestore_config_is_used_when_valid(self):
        db = FakeDb()
        db.store["system/class_registry/mtc13/main"] = {
            "display_name": "MTC13",
            "status": "active",
            "active_term_id": "2569-t1",
        }
        db.store["classes/mtc13/terms/2569-t1/config/timetable"] = build_timetable_config(SAMPLE_SCHEDULE)

        text = get_timetable_status_text(db, ClassContext("mtc13", "user-a"), monday(8, 40))

        self.assertIn("ฟิสิกส์", text)
        self.assertIn("เหลืออีก 45 นาที", text)

    def test_no_context_uses_mtc12_fallback(self):
        text = get_timetable_status_text(now=monday(8, 40))

        self.assertIn("ฟิสิกส์ (ครูจิราภรณ์)", text)

    def test_timetable_image_uses_firestore_image_url_when_available(self):
        db = FakeDb()
        db.store["system/class_registry/mtc13/main"] = {
            "display_name": "MTC13",
            "status": "active",
            "active_term_id": "2569-t1",
        }
        db.store["classes/mtc13/terms/2569-t1/config/timetable"] = {
            "timezone": "Asia/Bangkok",
            "image_url": "https://example.com/mtc13.png",
        }

        image_url = get_timetable_image_url(db, ClassContext("mtc13", "user-a"))

        self.assertEqual("https://example.com/mtc13.png", image_url)

    def test_mtc11_timetable_image_uses_class_specific_reviewed_url(self):
        db = FakeDb()
        db.store["system/class_registry/mtc11/main"] = {
            "display_name": "MTC11",
            "status": "active",
            "active_term_id": "2569-t1",
        }
        db.store["classes/mtc11/terms/2569-t1/config/timetable"] = {
            "timezone": "Asia/Bangkok",
            "image_url": "https://img2.pic.in.th/290922.jpg",
        }

        image_url = get_timetable_image_url(db, ClassContext("mtc11", "user-a"))

        self.assertEqual("https://img2.pic.in.th/290922.jpg", image_url)

    def test_non_legacy_class_missing_image_does_not_fallback_to_mtc12_image(self):
        db = FakeDb()
        db.store["system/class_registry/mtc11/main"] = {
            "display_name": "MTC11",
            "status": "active",
            "active_term_id": "2569-t1",
        }
        db.store["classes/mtc11/terms/2569-t1/config/timetable"] = build_timetable_config(SAMPLE_SCHEDULE)

        image_url = get_timetable_image_url(db, ClassContext("mtc11", "user-a"))
        message = get_timetable_image_message(db, ClassContext("mtc11", "user-a"))

        self.assertIsNone(image_url)
        self.assertIn("ยังไม่ได้ตั้งค่าภาพตารางเรียน", message.text)
        self.assertIn("MTC11", message.text)

    def test_invalid_firestore_config_falls_back_safely(self):
        db = FakeDb()
        db.store["system/class_registry/mtc13/main"] = {
            "display_name": "MTC13",
            "status": "active",
            "active_term_id": "2569-t1",
        }
        db.store["classes/mtc13/terms/2569-t1/config/timetable"] = {"days": "bad"}

        text = get_timetable_status_text(db, ClassContext("mtc13", "user-a"), monday(8, 40))

        self.assertNotIn("ฟิสิกส์ (ครูจิราภรณ์)", text)
        self.assertIn("ขออภัย ตารางเรียนของ MTC13 ยังไม่พร้อมใช้งานในขณะนี้", text)

    def test_mtc11_missing_timetable_does_not_use_global_mtc12_schedule(self):
        db = FakeDb()
        db.store["system/class_registry/mtc11/main"] = {
            "display_name": "MTC11",
            "status": "active",
            "active_term_id": "2569-t1",
        }
        # No config document at classes/mtc11/terms/2569-t1/config/timetable
        text = get_timetable_status_text(db, ClassContext("mtc11", "user-a"), monday(8, 40))
        self.assertNotIn("ฟิสิกส์ (ครูจิราภรณ์)", text)
        self.assertIn("ขออภัย ตารางเรียนของ MTC11 ยังไม่พร้อมใช้งานในขณะนี้", text)

    def test_mtc11_invalid_timetable_does_not_use_global_mtc12_schedule(self):
        db = FakeDb()
        db.store["system/class_registry/mtc11/main"] = {
            "display_name": "MTC11",
            "status": "active",
            "active_term_id": "2569-t1",
        }
        db.store["classes/mtc11/terms/2569-t1/config/timetable"] = {"days": "corrupted"}
        text = get_timetable_status_text(db, ClassContext("mtc11", "user-a"), monday(8, 40))
        self.assertNotIn("ฟิสิกส์ (ครูจิราภรณ์)", text)
        self.assertIn("ขออภัย ตารางเรียนของ MTC11 ยังไม่พร้อมใช้งานในขณะนี้", text)

    def test_mtc13_missing_timetable_does_not_use_global_mtc12_schedule(self):
        db = FakeDb()
        db.store["system/class_registry/mtc13/main"] = {
            "display_name": "MTC13",
            "status": "active",
            "active_term_id": "2569-t1",
        }
        # No config document at classes/mtc13/terms/2569-t1/config/timetable
        text = get_timetable_status_text(db, ClassContext("mtc13", "user-a"), monday(8, 40))
        self.assertNotIn("ฟิสิกส์ (ครูจิราภรณ์)", text)
        self.assertIn("ขออภัย ตารางเรียนของ MTC13 ยังไม่พร้อมใช้งานในขณะนี้", text)

    def test_explicit_mtc12_context_missing_config_does_not_silently_use_legacy_fallback(self):
        db = FakeDb()
        db.store["system/class_registry/mtc12/main"] = {
            "display_name": "MTC12",
            "status": "active",
            "active_term_id": "2569-t1",
        }
        # Explicitly not a legacy fallback context (is_legacy_fallback = False)
        text = get_timetable_status_text(db, ClassContext("mtc12", "user-a"), monday(8, 40))
        self.assertNotIn("ฟิสิกส์ (ครูจิราภรณ์)", text)
        self.assertIn("ขออภัย ตารางเรียนของ MTC12 ยังไม่พร้อมใช้งานในขณะนี้", text)

    def test_legacy_fallback_context_still_uses_schedule(self):
        db = FakeDb()
        # No database records, resolving legacy fallback context (is_legacy_fallback = True)
        text = get_timetable_status_text(db, ClassContext("mtc12", "user-a", is_legacy_fallback=True), monday(8, 40))
        self.assertIn("ฟิสิกส์ (ครูจิราภรณ์)", text)

    def test_valid_mtc11_timetable_still_works(self):
        db = FakeDb()
        db.store["system/class_registry/mtc11/main"] = {
            "display_name": "MTC11",
            "status": "active",
            "active_term_id": "2569-t1",
        }
        db.store["classes/mtc11/terms/2569-t1/config/timetable"] = build_timetable_config(SAMPLE_SCHEDULE)
        text = get_timetable_status_text(db, ClassContext("mtc11", "user-a"), monday(8, 40))
        self.assertIn("ฟิสิกส์", text)
        self.assertNotIn("ครูจิราภรณ์", text)

    def test_valid_mtc12_and_mtc13_timetable_behavior_remains_unchanged(self):
        db = FakeDb()
        db.store["system/class_registry/mtc12/main"] = {
            "display_name": "MTC12",
            "status": "active",
            "active_term_id": "2569-t1",
        }
        db.store["classes/mtc12/terms/2569-t1/config/timetable"] = build_timetable_config(SAMPLE_SCHEDULE)
        text12 = get_timetable_status_text(db, ClassContext("mtc12", "user-a"), monday(8, 40))
        self.assertIn("ฟิสิกส์", text12)

        db.store["system/class_registry/mtc13/main"] = {
            "display_name": "MTC13",
            "status": "active",
            "active_term_id": "2569-t1",
        }
        db.store["classes/mtc13/terms/2569-t1/config/timetable"] = build_timetable_config(SAMPLE_SCHEDULE)
        text13 = get_timetable_status_text(db, ClassContext("mtc13", "user-a"), monday(8, 40))
        self.assertIn("ฟิสิกส์", text13)

    def test_normalize_rejects_invalid_shape(self):
        self.assertIsNone(normalize_timetable_config({"days": "bad"}))
        self.assertIsNone(normalize_timetable_config({"days": {"x": []}}))
        self.assertIsNone(normalize_timetable_config({"days": {"0": [{"start": "bad"}]}}))


if __name__ == "__main__":
    unittest.main()
