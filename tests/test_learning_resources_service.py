import unittest

from mtc_assistant.class_context import ClassContext
from mtc_assistant.learning_resources_service import get_learning_resources


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
        if self.db.raise_on_get:
            raise RuntimeError("boom")
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

    def stream(self):
        if self.db.raise_on_stream:
            raise RuntimeError("boom")
        prefix = f"{self.path}/"
        docs = []
        for path, data in self.db.store.items():
            if path.startswith(prefix) and "/" not in path[len(prefix) :]:
                docs.append(FakeDocSnapshot(True, data))
        return docs


class FakeDb:
    def __init__(self):
        self.store = {}
        self.raise_on_get = False
        self.raise_on_stream = False

    def collection(self, name):
        return FakeCollection(self, name)


def non_legacy_context(class_id="mtc13"):
    return ClassContext(class_id, "user-a")


def legacy_context():
    return ClassContext("mtc12", "user-a", is_legacy_fallback=True)


def add_registry(db, class_id="mtc13", active_term_id="2569-t1", grade_level="m4"):
    data = {
        "display_name": class_id.upper(),
        "status": "active",
    }
    if active_term_id is not None:
        data["active_term_id"] = active_term_id
    if grade_level is not None:
        data["grade_level"] = grade_level
    db.store[f"system/class_registry/{class_id}/main"] = data


def add_resource(db, resource_id, data, class_id="mtc13", term_id="2569-t1"):
    db.store[f"classes/{class_id}/terms/{term_id}/resources/{resource_id}"] = data


def valid_resource(title="Biology Book", **overrides):
    data = {
        "section": "textbook_solutions",
        "type": "solution_manual",
        "subject_id": "biology",
        "subject_label": "Biology",
        "grade_level": "m4",
        "title": title,
        "url": "https://example.com/bio",
        "status": "active",
        "sort_order": 10,
    }
    data.update(overrides)
    return data


class LearningResourcesServiceTest(unittest.TestCase):
    def test_no_db_returns_empty_list(self):
        self.assertEqual([], get_learning_resources())

    def test_no_class_context_returns_empty_list(self):
        self.assertEqual([], get_learning_resources(FakeDb()))

    def test_legacy_fallback_context_returns_empty_list(self):
        self.assertEqual([], get_learning_resources(FakeDb(), legacy_context()))

    def test_missing_class_registry_returns_empty_list(self):
        self.assertEqual([], get_learning_resources(FakeDb(), non_legacy_context()))

    def test_missing_active_term_id_returns_empty_list(self):
        db = FakeDb()
        add_registry(db, active_term_id=None)

        self.assertEqual([], get_learning_resources(db, non_legacy_context()))

    def test_missing_resources_collection_returns_empty_list(self):
        db = FakeDb()
        add_registry(db)

        self.assertEqual([], get_learning_resources(db, non_legacy_context()))

    def test_active_valid_resource_is_returned(self):
        db = FakeDb()
        add_registry(db)
        add_resource(db, "bio-main", valid_resource(term_id=None))

        resources = get_learning_resources(db, non_legacy_context())

        self.assertEqual(1, len(resources))
        self.assertEqual("Biology Book", resources[0]["title"])
        self.assertEqual("https://example.com/bio", resources[0]["url"])
        self.assertEqual("2569-t1", resources[0]["term_id"])

    def test_missing_registry_grade_hides_textbook_solutions(self):
        db = FakeDb()
        add_registry(db, grade_level=None)
        add_resource(db, "bio-main", valid_resource())

        self.assertEqual([], get_learning_resources(db, non_legacy_context()))

    def test_invalid_registry_grade_hides_textbook_solutions(self):
        db = FakeDb()
        add_registry(db, grade_level="grade10")
        add_resource(db, "bio-main", valid_resource())

        self.assertEqual([], get_learning_resources(db, non_legacy_context()))

    def test_missing_resource_grade_hides_textbook_solutions(self):
        db = FakeDb()
        add_registry(db)
        add_resource(db, "bio-main", valid_resource(grade_level=None))

        self.assertEqual([], get_learning_resources(db, non_legacy_context()))

    def test_invalid_resource_grade_hides_textbook_solutions(self):
        db = FakeDb()
        add_registry(db)
        add_resource(db, "bio-main", valid_resource(grade_level="M4"))

        self.assertEqual([], get_learning_resources(db, non_legacy_context()))

    def test_mismatched_resource_grade_hides_textbook_solutions(self):
        db = FakeDb()
        add_registry(db, grade_level="m5")
        add_resource(db, "bio-main", valid_resource(grade_level="m4"))

        self.assertEqual([], get_learning_resources(db, non_legacy_context()))

    def test_m5_registry_cannot_receive_m4_solution_in_active_term(self):
        db = FakeDb()
        add_registry(db, active_term_id="2569-t1", grade_level="m5")
        add_resource(db, "bio-main", valid_resource(grade_level="m4"), term_id="2569-t1")

        self.assertEqual([], get_learning_resources(db, non_legacy_context()))

    def test_hidden_and_archived_resources_are_ignored(self):
        db = FakeDb()
        add_registry(db)
        add_resource(db, "hidden", valid_resource("Hidden", status="hidden"))
        add_resource(db, "archived", valid_resource("Archived", status="archived"))
        add_resource(db, "active", valid_resource("Active"))

        resources = get_learning_resources(db, non_legacy_context())

        self.assertEqual(["Active"], [resource["title"] for resource in resources])

    def test_invalid_blank_and_non_http_urls_are_ignored(self):
        db = FakeDb()
        add_registry(db)
        add_resource(db, "blank", valid_resource("Blank", url="   "))
        add_resource(db, "ftp", valid_resource("Ftp", url="ftp://example.com/file"))
        add_resource(db, "relative", valid_resource("Relative", url="/drive/file"))
        add_resource(db, "valid", valid_resource("Valid", url="http://example.com/file"))

        resources = get_learning_resources(db, non_legacy_context())

        self.assertEqual(["Valid"], [resource["title"] for resource in resources])

    def test_missing_title_is_ignored(self):
        db = FakeDb()
        add_registry(db)
        add_resource(db, "missing", valid_resource(title=None))
        add_resource(db, "blank", valid_resource(title="  "))
        add_resource(db, "valid", valid_resource("Valid"))

        resources = get_learning_resources(db, non_legacy_context())

        self.assertEqual(["Valid"], [resource["title"] for resource in resources])

    def test_missing_term_id_field_does_not_break_resource(self):
        db = FakeDb()
        add_registry(db)
        resource = valid_resource("No Term")
        resource.pop("term_id", None)
        add_resource(db, "no-term", resource)

        resources = get_learning_resources(db, non_legacy_context())

        self.assertEqual(1, len(resources))
        self.assertEqual("No Term", resources[0]["title"])
        self.assertEqual("2569-t1", resources[0]["term_id"])

    def test_conflicting_embedded_term_id_is_rejected(self):
        db = FakeDb()
        add_registry(db, active_term_id="2569-t1")
        add_resource(db, "wrong-term", valid_resource(term_id="2569-t2"), term_id="2569-t1")

        self.assertEqual([], get_learning_resources(db, non_legacy_context()))

    def test_subject_filter_works(self):
        db = FakeDb()
        add_registry(db)
        add_resource(db, "bio", valid_resource("Bio", subject_id="biology"))
        add_resource(db, "physics", valid_resource("Physics", subject_id="physics"))

        resources = get_learning_resources(db, non_legacy_context(), subject_id="physics")

        self.assertEqual(["Physics"], [resource["title"] for resource in resources])

    def test_section_filter_works(self):
        db = FakeDb()
        add_registry(db)
        add_resource(db, "solutions", valid_resource("Solutions", section="textbook_solutions"))
        add_resource(db, "assignments", valid_resource("Assignments", section="assignment_resources"))

        resources = get_learning_resources(db, non_legacy_context(), section="assignment_resources")

        self.assertEqual(["Assignments"], [resource["title"] for resource in resources])

    def test_assignment_resource_without_grade_remains_available(self):
        db = FakeDb()
        add_registry(db, grade_level=None)
        add_resource(
            db,
            "assignment",
            valid_resource(
                "Assignment",
                section="assignment_resources",
                type="worksheet_pack",
                subject_id=None,
                grade_level=None,
            ),
        )

        resources = get_learning_resources(
            db,
            non_legacy_context(),
            section="assignment_resources",
        )

        self.assertEqual(["Assignment"], [resource["title"] for resource in resources])

    def test_multiple_books_sort_by_sort_order_then_title(self):
        db = FakeDb()
        add_registry(db)
        add_resource(db, "z", valid_resource("Zeta", sort_order=2))
        add_resource(db, "b", valid_resource("Beta", sort_order=1))
        add_resource(db, "a", valid_resource("Alpha", sort_order=1))

        resources = get_learning_resources(db, non_legacy_context())

        self.assertEqual(["Alpha", "Beta", "Zeta"], [resource["title"] for resource in resources])

    def test_limit_caps_returned_resources(self):
        db = FakeDb()
        add_registry(db)
        for index in range(105):
            add_resource(db, f"resource-{index}", valid_resource(f"Resource {index:03}", sort_order=index))

        resources = get_learning_resources(db, non_legacy_context(), limit=200)

        self.assertEqual(100, len(resources))
        self.assertEqual("Resource 000", resources[0]["title"])
        self.assertEqual("Resource 099", resources[-1]["title"])

    def test_mtc13_does_not_receive_mtc12_resources(self):
        db = FakeDb()
        add_registry(db, "mtc13", "2569-t1")
        add_registry(db, "mtc12", "2568-t1")
        add_resource(db, "legacy-bio", valid_resource("MTC12 Bio"), class_id="mtc12", term_id="2568-t1")

        self.assertEqual([], get_learning_resources(db, non_legacy_context("mtc13")))

    def test_firestore_exception_returns_empty_list(self):
        db = FakeDb()
        db.raise_on_get = True

        self.assertEqual([], get_learning_resources(db, non_legacy_context()))

        db.raise_on_get = False
        db.raise_on_stream = True
        add_registry(db)

        self.assertEqual([], get_learning_resources(db, non_legacy_context()))


if __name__ == "__main__":
    unittest.main()
