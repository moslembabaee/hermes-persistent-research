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


class CrossSessionCliTests(unittest.TestCase):
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

    def test_clean_process_resumes_from_sqlite_without_chat_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "state.sqlite3"
            created = self.run_cli(
                db, "programme", "create", "--slug", "cross-session", "--title", "Cross session",
                "--objective", "Prove persistence", "--budget-json", '{"max_cycles":2}',
            )
            cycle = self.run_cli(
                db, "cycle", "start", "cross-session", "--objective", "First bounded cycle",
                "--budget-json", '{"max_sources":1}',
            )
            self.run_cli(
                db, "cycle", "checkpoint", "cross-session", "--cycle", cycle["cycle_id"],
                "--summary-json", '{"result":"checkpoint from process A"}',
            )

            # This is a separate process with only the stable slug and SQLite path.
            resumed = self.run_cli(db, "programme", "show", "cross-session")
            integrity = self.run_cli(db, "integrity")

            self.assertEqual(created["programme_id"], resumed["programme_id"])
            self.assertEqual("checkpoint from process A", json.loads(resumed["checkpoints"][0]["summary_json"])["result"])
            self.assertEqual("completed", resumed["cycles"][0]["status"])
            self.assertTrue(integrity["ok"])


if __name__ == "__main__":
    unittest.main()
