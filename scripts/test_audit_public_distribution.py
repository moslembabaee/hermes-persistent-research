from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from audit_public_distribution import audit, validate_env_example, validate_manifest, validate_version_consistency


REPO_ROOT = Path(__file__).resolve().parents[1]


class DistributionAuditTests(unittest.TestCase):
    def test_repository_passes_public_distribution_audit(self) -> None:
        self.assertEqual([], audit(REPO_ROOT))

    def test_manifest_rejects_default_name_and_cron(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "distribution.yaml").write_text(
                "name: default\nversion: 0.1.0\nhermes_requires: \">=0.21.6\"\n"
                "distribution_owned:\n  - cron\n",
                encoding="utf-8",
            )
            errors = validate_manifest(root)
            self.assertTrue(any("name must be pgra" in error for error in errors))
            self.assertTrue(any("cron must not be shipped" in error for error in errors))

    def test_env_example_rejects_populated_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".env.EXAMPLE").write_text("OPENAI_API_KEY=not-a-real-key\n", encoding="utf-8")
            errors = validate_env_example(root)
            self.assertEqual(1, len(errors))
            self.assertIn("must not contain a value", errors[0])

    def test_distribution_runtime_and_skill_versions_match(self) -> None:
        self.assertEqual([], validate_version_consistency(REPO_ROOT))


if __name__ == "__main__":
    unittest.main()
