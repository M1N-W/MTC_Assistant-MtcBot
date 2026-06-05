import unittest
from unittest.mock import patch

from flask import Flask

from mtc_assistant.admin_api import create_admin_api_blueprint
from mtc_assistant.links_service import (
    ABSENCE_FORM_URL,
    GRADE_URL,
    SCHOOL_URL,
    WORKSHEET_URL,
)


TOKEN = "test-dashboard-token"
BASE_PATH = "/api/admin/classes/mtc13/terms/2569-t1/config/links"


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

    def set(self, data, merge=False):
        if merge:
            current = dict(self.db.store.get(self.path, {}))
            current.update(data)
            self.db.store[self.path] = current
            return
        self.db.store[self.path] = dict(data)

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


def seed_class(db, class_id="mtc13", active_term_id="2569-t1"):
    db.store[f"system/class_registry/{class_id}/main"] = {
        "display_name": class_id.upper(),
        "status": "active",
        "active_term_id": active_term_id,
    }
    db.store[f"classes/{class_id}/terms/{active_term_id}/metadata/main"] = {
        "display_name": active_term_id,
        "status": "active",
    }


class AdminLinksApiTest(unittest.TestCase):
    def setUp(self):
        self.db = FakeDb()
        seed_class(self.db)
        app = Flask(__name__)
        app.register_blueprint(create_admin_api_blueprint(
            get_db=lambda: self.db,
            get_metrics=lambda: {},
            get_services=lambda: {},
        ))
        self.client = app.test_client()
        self.token_patch = patch("mtc_assistant.admin_api.MTC_DASHBOARD_API_TOKEN", TOKEN)
        self.token_patch.start()

    def tearDown(self):
        self.token_patch.stop()

    def auth(self):
        return {"Authorization": f"Bearer {TOKEN}"}

    def links_payload(self, **overrides):
        payload = {
            WORKSHEET_URL: "https://example.com/worksheet",
            SCHOOL_URL: "https://example.com/school",
            GRADE_URL: "https://example.com/grade",
            ABSENCE_FORM_URL: "https://example.com/absence",
        }
        payload.update(overrides)
        return payload

    def test_unauthorized_request_rejected(self):
        response = self.client.get(BASE_PATH)

        self.assertEqual(401, response.status_code)
        self.assertEqual("UNAUTHORIZED", response.get_json()["error"]["code"])

    def test_get_returns_existing_links(self):
        self.db.store["classes/mtc13/terms/2569-t1/config/links"] = {
            WORKSHEET_URL: "https://example.com/worksheet",
            SCHOOL_URL: "https://example.com/school",
            "unrelated": "kept-out-of-response",
        }

        response = self.client.get(BASE_PATH, headers=self.auth())
        data = response.get_json()["data"]

        self.assertEqual(200, response.status_code)
        self.assertEqual("mtc13", data["class_id"])
        self.assertEqual("https://example.com/worksheet", data["links"][WORKSHEET_URL])
        self.assertEqual("https://example.com/school", data["effective_links"][SCHOOL_URL])
        self.assertNotIn("unrelated", data["links"])

    def test_get_missing_links_doc_returns_blank_links_safely(self):
        response = self.client.get(BASE_PATH, headers=self.auth())
        data = response.get_json()["data"]

        self.assertEqual(200, response.status_code)
        self.assertEqual("", data["links"][WORKSHEET_URL])
        self.assertIn(SCHOOL_URL, data["effective_links"])

    def test_put_trims_values_and_writes_only_allowed_link_keys(self):
        response = self.client.put(BASE_PATH, headers=self.auth(), json=self.links_payload(
            worksheet_url="  https://example.com/worksheet  ",
            school_url="",
        ))

        written = self.db.store["classes/mtc13/terms/2569-t1/config/links"]
        self.assertEqual(200, response.status_code)
        self.assertEqual("https://example.com/worksheet", written[WORKSHEET_URL])
        self.assertEqual("", written[SCHOOL_URL])
        self.assertEqual("dashboard", written["updated_by"])
        self.assertIn("updated_at", written)

    def test_put_rejects_invalid_class_id(self):
        response = self.client.put(
            "/api/admin/classes/../mtc13/terms/2569-t1/config/links",
            headers=self.auth(),
            json=self.links_payload(),
        )

        self.assertIn(response.status_code, (404, 422))

    def test_put_rejects_invalid_term_id(self):
        response = self.client.put(
            "/api/admin/classes/mtc13/terms/../bad/config/links",
            headers=self.auth(),
            json=self.links_payload(),
        )

        self.assertIn(response.status_code, (404, 422))

    def test_put_rejects_unknown_extra_fields(self):
        response = self.client.put(BASE_PATH, headers=self.auth(), json={
            **self.links_payload(),
            "mtc_game_url": "https://example.com/game",
        })

        self.assertEqual(422, response.status_code)
        self.assertNotIn("classes/mtc13/terms/2569-t1/config/links", self.db.store)

    def test_put_rejects_non_string_values(self):
        response = self.client.put(BASE_PATH, headers=self.auth(), json=self.links_payload(
            grade_url=123,
        ))

        self.assertEqual(422, response.status_code)
        self.assertNotIn("classes/mtc13/terms/2569-t1/config/links", self.db.store)

    def test_put_rejects_http_url(self):
        response = self.client.put(BASE_PATH, headers=self.auth(), json=self.links_payload(
            school_url="http://example.com/school",
        ))

        self.assertEqual(422, response.status_code)
        self.assertNotIn("classes/mtc13/terms/2569-t1/config/links", self.db.store)

    def test_put_rejects_local_path(self):
        response = self.client.put(BASE_PATH, headers=self.auth(), json=self.links_payload(
            worksheet_url=r"C:\Users\User\secret.txt",
        ))

        self.assertEqual(422, response.status_code)
        self.assertNotIn("classes/mtc13/terms/2569-t1/config/links", self.db.store)

    def test_put_rejects_secret_looking_values(self):
        response = self.client.put(BASE_PATH, headers=self.auth(), json=self.links_payload(
            absence_form_url="https://example.com/form?token=abc123",
        ))

        self.assertEqual(422, response.status_code)
        self.assertNotIn("classes/mtc13/terms/2569-t1/config/links", self.db.store)

    def test_put_preserves_unrelated_existing_keys(self):
        self.db.store["classes/mtc13/terms/2569-t1/config/links"] = {
            "unrelated": "keep-me",
        }

        response = self.client.put(BASE_PATH, headers=self.auth(), json=self.links_payload())

        written = self.db.store["classes/mtc13/terms/2569-t1/config/links"]
        self.assertEqual(200, response.status_code)
        self.assertEqual("keep-me", written["unrelated"])
        self.assertNotIn("unrelated", response.get_json()["data"]["links"])

    def test_put_rejects_wrong_inactive_term(self):
        self.db.store["classes/mtc13/terms/2569-t2/metadata/main"] = {
            "display_name": "2569-t2",
            "status": "inactive",
        }

        response = self.client.put(
            "/api/admin/classes/mtc13/terms/2569-t2/config/links",
            headers=self.auth(),
            json=self.links_payload(),
        )

        self.assertEqual(422, response.status_code)
        self.assertNotIn("classes/mtc13/terms/2569-t2/config/links", self.db.store)


if __name__ == "__main__":
    unittest.main()
