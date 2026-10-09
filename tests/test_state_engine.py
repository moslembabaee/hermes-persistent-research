from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))

from pgra.db import Database, MigrationError
from pgra.service import DomainError, ResearchService


class StateEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "pgra.sqlite3"
        self.database = Database(self.db_path)
        self.service = ResearchService(self.database)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_fresh_migration_creates_schema_and_is_repeatable(self) -> None:
        self.database.migrate()
        with self.database.session() as connection:
            version = connection.execute("SELECT version FROM schema_migrations").fetchone()[0]
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(1, version)
        self.assertTrue({"programmes", "events", "evidence_items", "belief_revisions", "evaluation_runs"} <= tables)

    def test_migration_checksum_mismatch_is_rejected(self) -> None:
        migration_dir = Path(self.temp.name) / "migrations"
        migration_dir.mkdir()
        source = self.database.migration_dir / "001_initial.sql"
        target = migration_dir / source.name
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

        class LocalDatabase(Database):
            @property
            def migration_dir(self) -> Path:
                return migration_dir

        database = LocalDatabase(Path(self.temp.name) / "checksum.sqlite3")
        database.migrate()
        target.write_text(target.read_text(encoding="utf-8") + "\n-- changed\n", encoding="utf-8")
        with self.assertRaises(MigrationError):
            database.migrate()

    def test_events_are_append_only_and_stream_is_consistent(self) -> None:
        programme = self.service.create_programme("append-only", "Append only", "Prove event immutability")
        with self.database.session() as connection:
            event_id = connection.execute("SELECT event_id FROM events").fetchone()[0]
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("UPDATE events SET actor='changed' WHERE event_id=?", (event_id,))
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("DELETE FROM events WHERE event_id=?", (event_id,))
        integrity = self.database.integrity()
        self.assertTrue(integrity["ok"])
        self.assertEqual(1, programme["version"])

    def test_only_one_running_cycle_and_checkpoint_terminates_it(self) -> None:
        self.service.create_programme("cycles", "Cycles", "Bound execution")
        cycle = self.service.start_cycle("cycles", "Collect one source", {"max_sources": 1})
        with self.assertRaises(DomainError):
            self.service.start_cycle("cycles", "Second cycle", {})
        checkpoint = self.service.checkpoint("cycles", {"summary": "done"}, cycle["cycle_id"])
        state = self.service.get_programme("cycles")
        self.assertEqual("completed", state["cycles"][0]["status"])
        self.assertEqual(checkpoint["event_version"], state["version"])

    def test_paused_programme_cannot_start_cycle_until_resumed(self) -> None:
        self.service.create_programme("pause", "Pause", "Pause and resume")
        self.service.set_programme_status("pause", "paused", "operator pause")
        with self.assertRaises(DomainError):
            self.service.start_cycle("pause", "blocked while paused")
        self.service.set_programme_status("pause", "active", "operator resume")
        cycle = self.service.start_cycle("pause", "now allowed")
        self.assertEqual("running", cycle["status"])


if __name__ == "__main__":
    unittest.main()
