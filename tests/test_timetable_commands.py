# -*- coding: utf-8 -*-

import datetime
import unittest

from mtc_assistant import features, timetable_service
from mtc_assistant.class_context import ClassContext
from mtc_assistant.command_router import handle_standard_command
from mtc_assistant.config import LOCAL_TZ
from mtc_assistant.timetable_service import build_timetable_config


MTC13_SCHEDULE = {
    0: [
        {"start": "08:30", "end": "09:25", "subject": "MTC13 Only Physics", "room": "331"},
        {"start": "09:25", "end": "10:20", "subject": "MTC13 Only Math", "room": "632"},
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


class FixedDateTime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        value = monday(8, 40)
        return value if tz is None else value.astimezone(tz)


class TimetableCommandTest(unittest.TestCase):
    def setUp(self):
        self.original_db = features.db
        self.original_datetime = timetable_service.datetime.datetime
        timetable_service.datetime.datetime = FixedDateTime

        self.db = FakeDb()
        self.db.store["system/class_registry/mtc13/main"] = {
            "display_name": "MTC13",
            "status": "active",
            "active_term_id": "2569-t1",
        }
        self.db.store["classes/mtc13/terms/2569-t1/config/timetable"] = {
            **build_timetable_config(MTC13_SCHEDULE),
            "image_url": "https://example.com/mtc13.png",
        }
        features.db = self.db
        self.context = ClassContext("mtc13", "user-a")

    def tearDown(self):
        features.db = self.original_db
        timetable_service.datetime.datetime = self.original_datetime

    def test_timetable_image_commands_use_firestore_image_url(self):
        for command in ("ตารางเรียน", "ตารางสอน"):
            with self.subTest(command=command):
                message = handle_standard_command(command, command, self.context)

                self.assertEqual("https://example.com/mtc13.png", message.original_content_url)
                self.assertEqual("https://example.com/mtc13.png", message.preview_image_url)

    def test_time_status_commands_share_class_aware_logic(self):
        texts = []
        for command in ("เช็คเวลาเรียน", "เช็คเวลา", "อีกกี่นาที"):
            message = handle_standard_command(command, command, self.context)
            texts.append(message.text)

        self.assertEqual(texts[0], texts[1])
        self.assertEqual(texts[1], texts[2])
        self.assertIn("MTC13 Only Physics", texts[0])
        self.assertNotIn("ครูจิราภรณ์", texts[0])

    def test_next_class_command_uses_class_aware_timetable_source(self):
        message = handle_standard_command("คาบต่อไป", "คาบต่อไป", self.context)

        self.assertIn("MTC13 Only Physics", message.text)
        self.assertNotIn("ครูจิราภรณ์", message.text)

    def test_no_context_timetable_commands_keep_mtc12_fallback(self):
        status_message = handle_standard_command("เช็คเวลาเรียน", "เช็คเวลาเรียน")
        next_message = handle_standard_command("คาบต่อไป", "คาบต่อไป")

        self.assertIn("ครูจิราภรณ์", status_message.text)
        self.assertIn("ครูจิราภรณ์", next_message.text)


if __name__ == "__main__":
    unittest.main()
