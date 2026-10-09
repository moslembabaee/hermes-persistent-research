from __future__ import annotations

import json
import hashlib
import contextlib
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))

from pgra.db import Database
from pgra.cli import default_db_path
from pgra.evaluation import compare_runs
from pgra.service import DomainError, ResearchService


class ConsumerHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.database = Database(self.root / "state.sqlite3")
        self.service = ResearchService(self.database)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_projection_drift_is_detected_and_rebuilt_from_event(self) -> None:
        self.service.create_programme("rebuild", "Rebuild", "Prove projection repair")
        hypothesis = self.service.add_hypothesis(
            "rebuild", "The projection is accurate", "uncertain", "A drift check fails"
        )
        self.assertTrue(self.database.projection_status()["ok"])
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE hypotheses SET current_assessment='likely' WHERE hypothesis_id=?",
                (hypothesis["hypothesis_id"],),
            )
        self.assertFalse(self.database.projection_status()["ok"])
        rebuilt = self.database.rebuild_projection("rebuild")
        self.assertTrue(rebuilt["ok"])
        self.assertEqual(
            "uncertain",
            self.service.get_programme("rebuild")["hypotheses"][0]["current_assessment"],
        )
        self.assertTrue(self.database.projection_status()["ok"])

    def test_version_02_database_receives_rebuildable_baseline(self) -> None:
        legacy_path = self.root / "legacy.sqlite3"
        migration = (ROOT / "runtime" / "pgra" / "migrations" / "001_initial.sql").read_text(encoding="utf-8")
        checksum = hashlib.sha256(migration.encode("utf-8")).hexdigest()
        payload = json.dumps({"programme_id": "prg_legacy", "slug": "legacy"}, separators=(",", ":"), sort_keys=True)
        with contextlib.closing(sqlite3.connect(legacy_path)) as connection:
            connection.executescript(migration)
            connection.execute(
                "INSERT INTO schema_migrations VALUES(1,'001_initial.sql',?,'2026-01-01T00:00:00Z')",
                (checksum,),
            )
            connection.execute(
                "INSERT INTO programmes VALUES(?,?,?,?,?,?,?,?,?,?)",
                ("prg_legacy", "legacy", "Legacy", "Upgrade", "active", "{}", "{}", 1,
                 "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
            )
            connection.execute(
                """INSERT INTO events(event_id,programme_id,stream_version,event_type,occurred_at,actor,
                   schema_version,payload_json,payload_hash) VALUES(?,?,?,?,?,?,1,?,?)""",
                ("evt_legacy", "prg_legacy", 1, "ProgrammeCreated", "2026-01-01T00:00:00Z", "user",
                 payload, hashlib.sha256(payload.encode("utf-8")).hexdigest()),
            )
            connection.commit()
        upgraded = Database(legacy_path)
        upgraded.migrate()
        status = upgraded.projection_status()
        self.assertTrue(status["ok"])
        with upgraded.session() as connection:
            latest = connection.execute(
                "SELECT event_type,schema_version FROM events ORDER BY stream_version DESC LIMIT 1"
            ).fetchone()
        self.assertEqual("ProjectionBaselineCaptured", latest["event_type"])
        self.assertEqual(2, latest["schema_version"])

    def test_backup_and_restore_use_sqlite_backup_api(self) -> None:
        self.service.create_programme("backup", "Backup", "Prove recoverability")
        backup_path = self.root / "backups" / "state.sqlite3"
        result = self.database.backup(backup_path)
        self.assertEqual("ok", result["sqlite"])
        self.service.add_claim("backup", "This change happened after the backup")
        restored = self.database.restore(backup_path)
        self.assertTrue(restored["ok"])
        self.assertEqual([], self.service.get_programme("backup")["claims"])

    def test_budget_and_state_transitions_are_enforced(self) -> None:
        self.service.create_programme(
            "bounded", "Bounded", "Enforce limits", budget={"max_sources": 1, "max_cycles": 1}
        )
        self.service.add_source("bounded", "https://example.com/one", "One", "primary")
        with self.assertRaises(DomainError):
            self.service.add_source("bounded", "https://example.com/two", "Two", "primary")
        cycle = self.service.start_cycle("bounded", "Only cycle", {"max_sources": 1})
        self.service.checkpoint("bounded", {"result": "done"}, cycle["cycle_id"])
        with self.assertRaises(DomainError):
            self.service.start_cycle("bounded", "Extra cycle")
        self.service.set_programme_status("bounded", "completed", "work finished")
        with self.assertRaises(DomainError):
            self.service.set_programme_status("bounded", "active", "invalid reopen")

    def test_belief_revision_rejects_evidence_for_another_hypothesis(self) -> None:
        self.service.create_programme("beliefs", "Beliefs", "Keep triggers aligned")
        first = self.service.add_hypothesis("beliefs", "First", "uncertain", "Not first")
        second = self.service.add_hypothesis("beliefs", "Second", "uncertain", "Not second")
        source = self.service.add_source("beliefs", "https://example.com/source", "Source", "primary")
        snapshot = self.service.add_snapshot(
            "beliefs", source["source_id"], "https://example.com/source",
            locator="section 1", content_hash="b" * 64,
        )
        evidence = self.service.add_evidence(
            "beliefs", snapshot["snapshot_id"], "supports", "Observation", "Interpretation",
            source["source_id"], hypothesis_id=first["hypothesis_id"],
        )
        with self.assertRaises(DomainError):
            self.service.revise_belief(
                "beliefs", second["hypothesis_id"], "likely", "Wrong hypothesis",
                [evidence["evidence_id"]],
            )

    def test_snapshot_requires_verifiable_locator_and_hash(self) -> None:
        self.service.create_programme("snapshot", "Snapshot", "Keep evidence durable")
        source = self.service.add_source("snapshot", "https://example.com/source", "Source", "primary")
        with self.assertRaises(DomainError):
            self.service.add_snapshot("snapshot", source["source_id"], "https://example.com/source")

    def test_terminal_experiment_cannot_be_reauthorized_or_recompleted(self) -> None:
        self.service.create_programme("experiment", "Experiment", "Keep lifecycle valid")
        hypothesis = self.service.add_hypothesis("experiment", "Test", "uncertain", "No effect")
        experiment = self.service.create_experiment(
            "experiment", hypothesis["hypothesis_id"], "Run once", "Observe result",
            {"max_runs": 1}, "Stop after one run",
        )
        self.service.authorize_experiment("experiment", experiment["experiment_id"], True, "approved")
        self.service.complete_experiment("experiment", experiment["experiment_id"], "completed", {"ok": True})
        with self.assertRaises(DomainError):
            self.service.complete_experiment("experiment", experiment["experiment_id"], "completed", {"ok": True})
        with self.assertRaises(DomainError):
            self.service.authorize_experiment("experiment", experiment["experiment_id"], True, "again")

    def test_sanitized_export_and_report_are_consumer_readable(self) -> None:
        self.service.create_programme("report", "Report", "Readable output")
        export = self.service.sanitized_export("report")
        report = self.service.markdown_report("report")
        self.assertTrue(export["export"]["sanitized"])
        self.assertNotIn("events", export)
        self.assertIn("# Report", report)
        self.assertIn("## Counts", report)

    def test_evaluation_scores_must_be_normalized(self) -> None:
        with self.assertRaises(ValueError):
            compare_runs({"metrics": {"quality": 2}}, {"metrics": {"quality": 1}})

    def test_default_database_path_is_profile_local_not_global_hermes_home(self) -> None:
        with patch.dict("os.environ", {"HERMES_HOME": str(self.root / "global")}, clear=False):
            with patch.dict("os.environ", {"PGRA_DB": ""}, clear=False):
                path = default_db_path()
        self.assertEqual(ROOT / ".pgra" / "pgra.sqlite3", path)
        self.assertNotIn(str(self.root / "global"), str(path))


if __name__ == "__main__":
    unittest.main()
