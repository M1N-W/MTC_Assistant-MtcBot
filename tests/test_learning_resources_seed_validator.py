import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mtc_assistant.learning_resources_seed_validator import plan_learning_resources_seed


ROOT = Path(__file__).resolve().parents[1]


def resource(resource_id="bio-main", **overrides):
    data = {
        "id": resource_id,
        "class_id": "mtc13",
        "term_id": "2569-t1",
        "section": "textbook_solutions",
        "type": "solution_manual",
        "subject_id": "biology",
        "subject_label": "Biology",
        "grade_level": "m4",
        "title": "Biology Solutions",
        "url": "https://example.com/bio",
        "status": "active",
        "sort_order": 10,
    }
    data.update(overrides)
    return data


class LearningResourcesSeedValidatorTest(unittest.TestCase):
    def test_valid_minimal_seed_produces_create_without_errors(self):
        result = plan_learning_resources_seed([resource()])

        self.assertEqual([], result["errors"])
        self.assertEqual([], result["warnings"])
        self.assertEqual(["bio-main"], [item["id"] for item in result["would_create"]])

    def test_missing_class_id_produces_error(self):
        result = plan_learning_resources_seed([resource(class_id=" ")])

        self.assertTrue(any("class_id" in error["message"] for error in result["errors"]))

    def test_missing_term_id_produces_error(self):
        result = plan_learning_resources_seed([resource(term_id="")])

        self.assertTrue(any("term_id" in error["message"] for error in result["errors"]))

    def test_missing_id_produces_error(self):
        result = plan_learning_resources_seed([resource(resource_id="")])

        self.assertTrue(any("id" in error["message"] for error in result["errors"]))

    def test_unsafe_id_with_slash_produces_error(self):
        result = plan_learning_resources_seed([resource(resource_id="bio/main")])

        self.assertTrue(any("Firestore document ID" in error["message"] for error in result["errors"]))

    def test_empty_title_produces_error(self):
        result = plan_learning_resources_seed([resource(title="   ")])

        self.assertTrue(any("title" in error["message"] for error in result["errors"]))

    def test_invalid_url_produces_error(self):
        result = plan_learning_resources_seed([resource(url="not a url")])

        self.assertTrue(any("url" in error["message"] for error in result["errors"]))

    def test_http_url_is_rejected(self):
        result = plan_learning_resources_seed([resource(url="http://example.com/bio")])

        self.assertTrue(any("https" in error["message"] for error in result["errors"]))

    def test_local_file_path_is_rejected(self):
        result = plan_learning_resources_seed([resource(url="C:\\Users\\User\\bio.pdf")])

        self.assertTrue(any("local file path" in error["message"] for error in result["errors"]))

    def test_file_url_is_rejected(self):
        result = plan_learning_resources_seed([resource(url="file:///Users/user/bio.pdf")])

        self.assertTrue(any("local file path" in error["message"] for error in result["errors"]))

    def test_unc_path_is_rejected(self):
        result = plan_learning_resources_seed([resource(url="\\\\server\\share\\bio.pdf")])

        self.assertTrue(any("local file path" in error["message"] for error in result["errors"]))

    def test_home_relative_path_is_rejected(self):
        result = plan_learning_resources_seed([resource(url="~/Downloads/bio.pdf")])

        self.assertTrue(any("local file path" in error["message"] for error in result["errors"]))

    def test_mnt_c_path_is_rejected(self):
        result = plan_learning_resources_seed([resource(url="/mnt/c/Users/example/bio.pdf")])

        self.assertTrue(any("local file path" in error["message"] for error in result["errors"]))

    def test_etc_path_is_rejected(self):
        result = plan_learning_resources_seed([resource(url="/etc/hosts")])

        self.assertTrue(any("local file path" in error["message"] for error in result["errors"]))

    def test_secret_looking_value_is_rejected(self):
        result = plan_learning_resources_seed([resource(description="TOKEN=abc123")])

        self.assertTrue(any("secret" in error["message"] for error in result["errors"]))

    def test_bearer_token_without_dots_is_rejected(self):
        token = "Bearer abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        result = plan_learning_resources_seed([resource(description=token)])

        self.assertTrue(any("secret" in error["message"] for error in result["errors"]))

    def test_long_token_assignment_without_dots_is_rejected(self):
        token = "TOKEN=abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        result = plan_learning_resources_seed([resource(description=token)])

        self.assertTrue(any("secret" in error["message"] for error in result["errors"]))

    def test_long_https_url_is_not_rejected_as_token(self):
        result = plan_learning_resources_seed([
            resource(url="https://example.com/resources/" + ("a" * 80) + "/biology")
        ])

        self.assertEqual([], result["errors"])

    def test_status_accepts_supported_values(self):
        result = plan_learning_resources_seed([
            resource("active", status="active"),
            resource("hidden", status="hidden"),
            resource("archived", status="archived"),
        ])

        self.assertEqual([], result["errors"])

    def test_enabled_is_rejected_as_obsolete(self):
        result = plan_learning_resources_seed([resource(enabled=True)])

        self.assertTrue(any("enabled is obsolete" in error["message"] for error in result["errors"]))

    def test_invalid_status_is_rejected(self):
        result = plan_learning_resources_seed([resource(status="enabled")])

        self.assertTrue(any("status" in error["message"] for error in result["errors"]))

    def test_textbook_solutions_require_grade_level(self):
        result = plan_learning_resources_seed([resource(grade_level="")])

        self.assertTrue(any("grade_level" in error["message"] for error in result["errors"]))

    def test_textbook_solutions_reject_invalid_grade_level(self):
        result = plan_learning_resources_seed([resource(grade_level="M4")])

        self.assertTrue(any("grade_level" in error["message"] for error in result["errors"]))

    def test_duplicate_resource_id_in_same_class_term_produces_error(self):
        result = plan_learning_resources_seed([
            resource("bio-main"),
            resource("bio-main", title="Biology Copy"),
        ])

        self.assertTrue(any("Duplicate resource id" in error["message"] for error in result["errors"]))

    def test_same_resource_id_across_different_class_or_term_is_allowed(self):
        result = plan_learning_resources_seed([
            resource("shared-id", class_id="mtc13", term_id="2569-t1"),
            resource("shared-id", class_id="mtc14", term_id="2570-t1"),
        ])

        self.assertEqual([], result["errors"])
        self.assertEqual(["shared-id", "shared-id"], [item["id"] for item in result["would_create"]])

    def test_textbook_solutions_without_subject_id_fails(self):
        result = plan_learning_resources_seed([resource(subject_id="")])

        self.assertTrue(any("subject_id" in error["message"] for error in result["errors"]))

    def test_textbook_solutions_rejects_miscased_subject_id(self):
        result = plan_learning_resources_seed([resource(subject_id="BioLogy")])

        self.assertTrue(any("subject_id" in error["message"] for error in result["errors"]))

    def test_textbook_solutions_rejects_alias_subject_id(self):
        result = plan_learning_resources_seed([resource(subject_id="bio")])

        self.assertTrue(any("subject_id" in error["message"] for error in result["errors"]))

    def test_textbook_solutions_allows_supported_subject_ids(self):
        result = plan_learning_resources_seed([
            resource("bio-main", subject_id="biology"),
            resource("physics-main", subject_id="physics"),
        ])

        self.assertEqual([], result["errors"])

    def test_non_subject_specific_resource_without_subject_id_can_pass(self):
        result = plan_learning_resources_seed([
            resource(
                "assignment-pack",
                section="assignment_resources",
                type="worksheet_pack",
                subject_id="",
                title="Assignment Pack",
            )
        ])

        self.assertEqual([], result["errors"])

    def test_provided_subject_id_must_be_safe(self):
        result = plan_learning_resources_seed([
            resource("assignment-pack", section="assignment_resources", type="worksheet_pack", subject_id="bad/id")
        ])

        self.assertTrue(any("subject_id" in error["message"] for error in result["errors"]))

    def test_duplicate_active_textbook_solution_collision_fails(self):
        result = plan_learning_resources_seed([
            resource("bio-main"),
            resource("bio-alt", title="Biology Alt"),
        ])

        self.assertTrue(any("textbook_solutions" in error["message"] for error in result["errors"]))

    def test_non_active_textbook_solutions_do_not_collide(self):
        result = plan_learning_resources_seed([
            resource("bio-hidden", status="hidden"),
            resource("bio-archived", status="archived"),
        ])

        self.assertEqual([], result["errors"])

    def test_allow_multiple_escape_hatch_allows_textbook_solution_collision(self):
        result = plan_learning_resources_seed([
            resource("bio-main", allow_multiple=True),
            resource("bio-alt", title="Biology Alt", allow_multiple=True),
        ])

        self.assertEqual([], result["errors"])

    def test_general_link_fields_produce_warning(self):
        result = plan_learning_resources_seed([resource(worksheet_url="https://example.com/worksheet")])

        self.assertTrue(any("config/links" in warning["message"] for warning in result["warnings"]))

    def test_would_skip_for_identical_existing_record(self):
        seed = resource()
        result = plan_learning_resources_seed([seed], existing_resources=[dict(seed)])

        self.assertEqual(["bio-main"], [item["id"] for item in result["would_skip"]])

    def test_would_update_for_changed_existing_record(self):
        seed = resource(title="Updated Biology")
        existing = resource(title="Old Biology")

        result = plan_learning_resources_seed([seed], existing_resources=[existing])

        self.assertEqual(["bio-main"], [item["id"] for item in result["would_update"]])

    def test_would_disable_for_active_existing_record_missing_from_seed(self):
        result = plan_learning_resources_seed(
            [resource("bio-main")],
            existing_resources=[resource("old-bio", title="Old Biology")],
        )

        self.assertEqual(["old-bio"], [item["id"] for item in result["would_disable"]])

    def test_non_active_existing_record_missing_from_seed_does_not_disable(self):
        result = plan_learning_resources_seed(
            [resource("bio-main")],
            existing_resources=[
                resource("old-hidden", title="Old Hidden", status="hidden"),
                resource("old-archived", title="Old Archived", status="archived"),
            ],
        )

        self.assertEqual([], result["would_disable"])

    def test_no_would_delete_category_exists(self):
        result = plan_learning_resources_seed([resource()])

        self.assertNotIn("would_delete", result)

    def test_output_ordering_is_deterministic(self):
        result = plan_learning_resources_seed([
            resource("z", class_id="mtc14", term_id="2570-t1"),
            resource("a", class_id="mtc13", term_id="2569-t1", subject_id="physics"),
        ])

        self.assertEqual(["a", "z"], [item["id"] for item in result["would_create"]])

    def test_class_isolation_does_not_disable_unrelated_class_term(self):
        result = plan_learning_resources_seed(
            [resource("bio-main", class_id="mtc13", term_id="2569-t1")],
            existing_resources=[resource("mtc12-bio", class_id="mtc12", term_id="2568-t1")],
        )

        self.assertEqual([], result["would_disable"])

    def test_private_student_fields_are_rejected(self):
        result = plan_learning_resources_seed([resource(student_id="12345")])

        self.assertTrue(any("private student" in error["message"] for error in result["errors"]))


class LearningResourcesSeedCliTest(unittest.TestCase):
    def run_cli(self, payload):
        with tempfile.TemporaryDirectory() as temp_dir:
            seed_path = Path(temp_dir) / "seed.json"
            seed_path.write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "validate_learning_resources_seed.py"), "--seed", str(seed_path)],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
                check=False,
            )

    def test_cli_exits_zero_on_valid_seed(self):
        completed = self.run_cli({"resources": [resource()]})

        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertIn("would_create", completed.stdout)

    def test_cli_exits_non_zero_on_validation_errors(self):
        completed = self.run_cli({"resources": [resource(url="http://example.com/bio")]})

        self.assertNotEqual(0, completed.returncode)
        self.assertIn("errors", completed.stdout)


if __name__ == "__main__":
    unittest.main()
