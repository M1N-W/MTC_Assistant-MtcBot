import datetime
import unittest
from unittest.mock import patch

from flask import Flask

from mtc_assistant.admin_api import create_admin_api_blueprint


TOKEN = "test-dashboard-token"


class FakeSnapshot:
    def __init__(self, doc_id, data=None, exists=True):
        self.id = doc_id
        self._data = data or {}
        self.exists = exists

    def to_dict(self):
        return dict(self._data)


class FakeCountResult:
    def __init__(self, value):
        self.value = value


class FakeCountQuery:
    def __init__(self, values):
        self.values = values

    def get(self):
        return [[FakeCountResult(len(self.values))]]


class FakeQuery:
    def __init__(self, values):
        self.values = list(values)
        self.limit_value = None

    def order_by(self, _field, direction=None):
        del direction
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def stream(self):
        values = self.values
        if self.limit_value is not None:
            values = values[: self.limit_value]
        return iter(values)


class FakeCollection:
    def __init__(self, db, path):
        self.db = db
        self.path = path
        self.id = path.rsplit("/", 1)[-1]

    def document(self, doc_id):
        return FakeDocRef(self.db, f"{self.path}/{doc_id}")

    def order_by(self, field, direction=None):
        values = sorted(
            self.db.collections.get(self.path, []),
            key=lambda item: str(item.to_dict().get(field) or ""),
            reverse=True,
        )
        return FakeQuery(values).order_by(field, direction=direction)

    def count(self):
        return FakeCountQuery(self.db.collections.get(self.path, []))


class FakeDocRef:
    def __init__(self, db, path):
        self.db = db
        self.path = path

    def get(self):
        data = self.db.documents.get(self.path)
        return FakeSnapshot(self.path.rsplit("/", 1)[-1], data, data is not None)

    def collection(self, name):
        return FakeCollection(self.db, f"{self.path}/{name}")

    def collections(self):
        prefix = f"{self.path}/"
        names = {
            path[len(prefix):].split("/", 1)[0]
            for path in self.db.documents
            if path.startswith(prefix)
        }
        return iter(FakeCollection(self.db, f"{self.path}/{name}") for name in sorted(names))


class FakeDb:
    def __init__(self):
        self.documents = {}
        self.collections = {}

    def collection(self, name):
        return FakeCollection(self, name)


def seed_workspace(
    db,
    class_id="mtc13",
    display_name="MTC13",
    active_term_id="2569-t1",
    term_name="ภาคเรียนที่ 1/2569",
):
    db.documents[f"system/class_registry/{class_id}/main"] = {
        "display_name": display_name,
        "status": "active",
        "active_term_id": active_term_id,
        "secret": "must-not-leak",
    }
    db.documents[f"classes/{class_id}/terms/{active_term_id}/metadata/main"] = {
        "display_name": term_name,
        "status": "active",
        "internal": "must-not-leak",
    }


class AdminApiTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDb()
        app = Flask(__name__)
        app.register_blueprint(
            create_admin_api_blueprint(
                get_db=lambda: self.db,
                get_metrics=lambda: {},
                get_services=lambda: {},
            )
        )
        self.client = app.test_client()
        self.token_patch = patch(
            "mtc_assistant.admin_api.MTC_DASHBOARD_API_TOKEN", TOKEN
        )
        self.token_patch.start()

    def tearDown(self):
        self.token_patch.stop()

    def auth(self):
        return {"Authorization": f"Bearer {TOKEN}"}

    def test_overview_excludes_sustainability_without_calculating_it(self):
        with (
            patch(
                "mtc_assistant.admin_api._build_sustainability_impact"
            ) as build_sustainability,
            patch(
                "mtc_assistant.admin_api._get_recent_homeworks",
                return_value=[],
            ),
            patch(
                "mtc_assistant.admin_api._get_recent_broadcasts",
                return_value=[],
            ),
            patch("mtc_assistant.admin_api.get_blacklist_manager") as blacklist,
            patch("mtc_assistant.admin_api.broadcast.get_user_count", return_value=0),
        ):
            blacklist.return_value.get_all_banned.return_value = []

            response = self.client.get("/api/admin/overview", headers=self.auth())

        self.assertEqual(200, response.status_code)
        self.assertNotIn("sustainability", response.get_json()["data"])
        build_sustainability.assert_not_called()

    def test_workspaces_returns_safe_human_readable_entries(self):
        seed_workspace(self.db)

        response = self.client.get("/api/admin/workspaces", headers=self.auth())
        payload = response.get_json()

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            [
                {
                    "class_id": "mtc13",
                    "label": "MTC13",
                    "active_term_id": "2569-t1",
                    "active_term_label": "ภาคเรียนที่ 1/2569",
                    "status": "active",
                    "can_edit_active_term": True,
                }
            ],
            payload["data"]["workspaces"],
        )
        self.assertNotIn("secret", str(payload))
        self.assertNotIn("internal", str(payload))

    def test_workspaces_skips_invalid_or_incomplete_registry_entries(self):
        seed_workspace(self.db)
        self.db.documents["system/class_registry/bad id/main"] = {
            "display_name": "Bad",
            "status": "active",
            "active_term_id": "2569-t1",
        }
        self.db.documents["system/class_registry/mtc14/main"] = {
            "display_name": "",
            "status": "active",
            "active_term_id": "2569-t1",
        }

        response = self.client.get("/api/admin/workspaces", headers=self.auth())

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(response.get_json()["data"]["workspaces"]))

    def test_workspaces_handles_firebase_unavailable(self):
        app = Flask(__name__)
        app.register_blueprint(
            create_admin_api_blueprint(
                get_db=lambda: None,
                get_metrics=lambda: {},
                get_services=lambda: {},
            )
        )

        response = app.test_client().get(
            "/api/admin/workspaces", headers=self.auth()
        )

        self.assertEqual(503, response.status_code)
        self.assertEqual("FIREBASE_UNAVAILABLE", response.get_json()["error"]["code"])

    def test_paperless_summary_returns_empty_factual_state(self):
        response = self.client.get(
            "/api/admin/paperless-captures/summary", headers=self.auth()
        )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "successful_capture_count": 0,
                "latest_success_at": None,
                "recent": [],
            },
            response.get_json()["data"],
        )

    def test_paperless_summary_returns_bounded_safe_metadata(self):
        records = []
        for index in range(14):
            records.append(
                FakeSnapshot(
                    f"capture-{index}",
                    {
                        "timestamp": (
                            datetime.datetime(2026, 6, 13, 8, index).isoformat()
                        ),
                        "created_at": (
                            datetime.datetime(2026, 6, 13, 8, index).isoformat()
                        ),
                        "mime_type": "image/jpeg",
                        "image_size_bytes": 1000 + index,
                        "analysis": {
                            "summary": ["one", "two"],
                            "homework_candidates": ["candidate"],
                            "raw_text": "private extracted text",
                        },
                        "image_bytes": "must-not-leak",
                        "api_key": "must-not-leak",
                    },
                )
            )
        self.db.collections["paperless_captures"] = records

        response = self.client.get(
            "/api/admin/paperless-captures/summary", headers=self.auth()
        )
        data = response.get_json()["data"]

        self.assertEqual(200, response.status_code)
        self.assertEqual(14, data["successful_capture_count"])
        self.assertEqual(10, len(data["recent"]))
        self.assertEqual("capture-13", data["recent"][0]["id"])
        self.assertEqual("capture-4", data["recent"][-1]["id"])
        self.assertEqual("2026-06-13T08:13:00", data["latest_success_at"])
        self.assertEqual(2, data["recent"][0]["summary_item_count"])
        self.assertEqual(1, data["recent"][0]["homework_candidate_count"])
        self.assertNotIn("raw_text", str(data))
        self.assertNotIn("image_bytes", str(data))
        self.assertNotIn("api_key", str(data))

    def test_paperless_summary_handles_malformed_legacy_record(self):
        self.db.collections["paperless_captures"] = [
            FakeSnapshot("legacy", {"analysis": "unexpected", "mime_type": 123})
        ]

        response = self.client.get(
            "/api/admin/paperless-captures/summary", headers=self.auth()
        )
        data = response.get_json()["data"]

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, data["successful_capture_count"])
        self.assertEqual(1, len(data["recent"]))
        self.assertEqual(0, data["recent"][0]["summary_item_count"])
        self.assertEqual(0, data["recent"][0]["homework_candidate_count"])

    def test_paperless_summary_handles_firebase_unavailable(self):
        app = Flask(__name__)
        app.register_blueprint(
            create_admin_api_blueprint(
                get_db=lambda: None,
                get_metrics=lambda: {},
                get_services=lambda: {},
            )
        )

        response = app.test_client().get(
            "/api/admin/paperless-captures/summary", headers=self.auth()
        )

        self.assertEqual(503, response.status_code)
        self.assertEqual("FIREBASE_UNAVAILABLE", response.get_json()["error"]["code"])


if __name__ == "__main__":
    unittest.main()
