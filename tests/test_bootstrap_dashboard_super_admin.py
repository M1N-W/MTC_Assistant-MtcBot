import datetime
import io
import os
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from mtc_assistant.bootstrap_dashboard_super_admin import (
    bootstrap_super_admin,
    main,
)


UTC = datetime.timezone.utc


class FakeRepository:
    def __init__(self):
        self.bootstrap_calls = []

    def project_id(self):
        return "actual-project"

    def bootstrap_super_admin(self, account, username_digest, audit):
        self.bootstrap_calls.append((account, username_digest, audit))


class DuplicateGuardRepository(FakeRepository):
    def bootstrap_super_admin(self, account, username_digest, audit):
        raise ValueError("super admin bootstrap already completed")


class BootstrapDashboardSuperAdminTest(unittest.TestCase):
    def test_bootstrap_creates_super_admin_through_atomic_repository_operation(self):
        repository = FakeRepository()
        account = bootstrap_super_admin(
            repository,
            username="first.admin",
            password="correct horse battery staple",
            now=datetime.datetime(2026, 6, 14, tzinfo=UTC),
        )
        self.assertEqual("super_admin", account.role)
        self.assertEqual(1, len(repository.bootstrap_calls))
        self.assertEqual("super_admin_bootstrap", repository.bootstrap_calls[0][2].event_type)

    def test_cli_refuses_project_confirmation_mismatch_before_password_prompt(self):
        repository = FakeRepository()
        output = io.StringIO()
        prompted = []

        result = main(
            ["--project-id", "wrong-project", "--username", "first.admin"],
            repository_factory=lambda: repository,
            input_fn=lambda prompt: "wrong-project",
            getpass_fn=lambda prompt: prompted.append(prompt) or "not-used",
            stdout=output,
        )

        self.assertEqual(2, result)
        self.assertEqual([], prompted)
        self.assertEqual([], repository.bootstrap_calls)
        self.assertNotIn("password", output.getvalue().lower())

    def test_cli_reads_password_twice_and_never_prints_it(self):
        repository = FakeRepository()
        output = io.StringIO()
        passwords = iter(
            ["correct horse battery staple", "correct horse battery staple"]
        )
        result = main(
            ["--project-id", "actual-project", "--username", "first.admin"],
            repository_factory=lambda: repository,
            input_fn=lambda prompt: "actual-project",
            getpass_fn=lambda prompt: next(passwords),
            stdout=output,
        )
        self.assertEqual(0, result)
        self.assertEqual(1, len(repository.bootstrap_calls))
        self.assertNotIn("correct horse", output.getvalue())
        self.assertNotIn(repository.bootstrap_calls[0][0].password_hash, output.getvalue())

    def test_cli_refuses_duplicate_bootstrap(self):
        output = io.StringIO()
        passwords = iter(
            ["correct horse battery staple", "correct horse battery staple"]
        )
        result = main(
            ["--project-id", "actual-project", "--username", "first.admin"],
            repository_factory=DuplicateGuardRepository,
            input_fn=lambda prompt: "actual-project",
            getpass_fn=lambda prompt: next(passwords),
            stdout=output,
        )
        self.assertEqual(2, result)
        self.assertIn("refused", output.getvalue())

    def test_cli_does_not_accept_password_argument(self):
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main(
                    [
                        "--project-id",
                        "actual-project",
                        "--username",
                        "first.admin",
                        "--password",
                        "must-not-be-accepted",
                    ],
                    repository_factory=FakeRepository,
                )

    def test_cli_ignores_environment_password_and_uses_getpass(self):
        repository = FakeRepository()
        output = io.StringIO()
        prompts = []
        passwords = iter(
            ["correct horse battery staple", "correct horse battery staple"]
        )
        with patch.dict(
            os.environ,
            {"DASHBOARD_BOOTSTRAP_PASSWORD": "must-not-be-used"},
        ):
            result = main(
                [
                    "--project-id",
                    "actual-project",
                    "--username",
                    "first.admin",
                ],
                repository_factory=lambda: repository,
                input_fn=lambda prompt: "actual-project",
                getpass_fn=lambda prompt: prompts.append(prompt)
                or next(passwords),
                stdout=output,
            )
        self.assertEqual(0, result)
        self.assertEqual(2, len(prompts))
        self.assertNotIn("must-not-be-used", output.getvalue())


if __name__ == "__main__":
    unittest.main()
