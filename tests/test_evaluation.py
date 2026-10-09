from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))

from pgra.db import Database
from pgra.evaluation import compare_runs
from pgra.service import ResearchService


class EvaluationTests(unittest.TestCase):
    def test_compare_runs_reports_deltas_and_condition_mismatch(self) -> None:
        baseline = {"metrics": {"correctness": 0.6, "provenance": 0.4}, "conditions": {"model": "same"}}
        pgra = {"metrics": {"correctness": 0.8, "provenance": 0.9}, "conditions": {"model": "same"}}
        result = compare_runs(baseline, pgra)
        self.assertTrue(result["comparable"])
        self.assertAlmostEqual(0.35, result["summary"]["mean_delta"])
        self.assertEqual(2, result["summary"]["pgra_wins"])

    def test_evaluation_is_persisted_and_evented(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            service = ResearchService(Database(Path(temp) / "state.sqlite3"))
            service.create_programme("evaluation", "Evaluation", "Compare with baseline")
            baseline = {"metrics": {"correctness": 0.5}, "conditions": {"budget": 10}, "cost": {"usd": 1}}
            pgra = {"metrics": {"correctness": 0.7}, "conditions": {"budget": 10}, "cost": {"usd": 2}}
            evaluation = service.record_evaluation("evaluation", "synthetic-v1", baseline, pgra)
            state = service.get_programme("evaluation")
            self.assertEqual("synthetic-v1", evaluation["benchmark_name"])
            self.assertEqual("EvaluationCompleted", state["events"][-1]["event_type"])


if __name__ == "__main__":
    unittest.main()
