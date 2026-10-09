from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "pgra.py"


class FullCliWorkflowTests(unittest.TestCase):
    def run_cli(self, db: Path, *args: str) -> dict:
        result = subprocess.run(
            [sys.executable, str(CLI), "--db", str(db), *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        return json.loads(result.stdout)

    def test_evidence_revision_and_evaluation_through_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / "state.sqlite3"
            self.run_cli(db, "programme", "create", "--slug", "full-cli", "--title", "Full CLI",
                         "--objective", "Exercise the public command surface")
            hypothesis = self.run_cli(
                db, "hypothesis", "add", "full-cli", "--statement", "Persistence improves provenance",
                "--assessment", "uncertain", "--falsifier", "No measurable provenance improvement",
            )
            claim = self.run_cli(db, "claim", "add", "full-cli", "--statement", "The source has a stable identity")
            source = self.run_cli(
                db, "source", "add", "full-cli", "--uri", "https://example.com/primary",
                "--title", "Primary source", "--type", "primary",
            )
            snapshot = self.run_cli(
                db, "source", "snapshot", "full-cli", source["source_id"],
                "--observed-uri", "https://example.com/primary", "--locator", "section-1",
                "--content-hash", "a" * 64,
            )
            evidence = self.run_cli(
                db, "evidence", "add", "full-cli", "--snapshot", snapshot["snapshot_id"],
                "--claim", claim["claim_id"], "--hypothesis", hypothesis["hypothesis_id"],
                "--stance", "supports", "--observation", "Stable source identity recorded",
                "--interpretation", "Provenance is inspectable", "--lineage-group", source["source_id"], "--verified",
            )
            revision = self.run_cli(
                db, "hypothesis", "revise", "full-cli", hypothesis["hypothesis_id"],
                "--assessment", "likely", "--reasoning", "Verified evidence supports the hypothesis",
                "--evidence", evidence["evidence_id"],
            )
            baseline_path = root / "baseline.json"
            pgra_path = root / "pgra.json"
            baseline_path.write_text(json.dumps({"metrics": {"provenance": 0.4}, "conditions": {"budget": 1}}), encoding="utf-8")
            pgra_path.write_text(json.dumps({"metrics": {"provenance": 0.8}, "conditions": {"budget": 1}}), encoding="utf-8")
            evaluation = self.run_cli(
                db, "evaluation", "compare", "--programme", "full-cli", "--name", "cli-synthetic",
                "--baseline", str(baseline_path), "--pgra", str(pgra_path),
            )
            state = self.run_cli(db, "programme", "show", "full-cli")
            self.assertEqual("likely", revision["new_assessment"])
            self.assertAlmostEqual(0.4, evaluation["result"]["summary"]["mean_delta"])
            self.assertEqual(1, len(state["evidence"]))
            self.assertEqual(1, len(state["belief_revisions"]))
            self.assertEqual(1, len(state["evaluations"]))

    def test_consumer_inspection_recovery_and_export_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            db = root / "state.sqlite3"
            self.run_cli(
                db, "programme", "create", "--slug", "consumer", "--title", "Consumer",
                "--objective", "Exercise consumer commands",
            )
            summary = self.run_cli(db, "programme", "summary", "consumer")
            report_path = root / "report.md"
            export_path = root / "export.json"
            backup_path = root / "backup.sqlite3"
            report = self.run_cli(db, "programme", "report", "consumer", "--output", str(report_path))
            export = self.run_cli(db, "programme", "export", "consumer", "--output", str(export_path))
            backup = self.run_cli(db, "backup", "create", str(backup_path))
            projection = self.run_cli(db, "projection", "status")
            doctor = self.run_cli(db, "doctor")
            templates = self.run_cli(db, "evaluation", "template", "--directory", str(root / "evaluation"))

            self.assertEqual("consumer", summary["slug"])
            self.assertTrue(report_path.is_file())
            self.assertTrue(export_path.is_file())
            self.assertTrue(backup_path.is_file())
            self.assertTrue(report["ok"] and export["sanitized"] and backup["ok"])
            self.assertTrue(projection["ok"] and doctor["ok"])
            self.assertEqual(3, len(templates["files"]))


if __name__ == "__main__":
    unittest.main()
