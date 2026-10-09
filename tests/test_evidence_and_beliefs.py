from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))

from pgra.db import Database
from pgra.service import DomainError, ResearchService


class EvidenceAndBeliefTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.service = ResearchService(Database(Path(self.temp.name) / "state.sqlite3"))
        self.service.create_programme("evidence", "Evidence", "Test provenance")
        self.hypothesis = self.service.add_hypothesis(
            "evidence", "The intervention improves quality", "uncertain", "A controlled test shows no improvement"
        )
        self.claim = self.service.add_claim("evidence", "Measured quality increased")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def add_source_snapshot(self, uri: str, title: str):
        source = self.service.add_source("evidence", uri, title, "primary")
        snapshot = self.service.add_snapshot(
            "evidence", source["source_id"], uri, locator="section 1", content_hash="a" * 64
        )
        return source, snapshot

    def test_support_and_counterevidence_are_preserved_with_lineage(self) -> None:
        source_a, snapshot_a = self.add_source_snapshot("https://example.com/study", "Study")
        source_b, snapshot_b = self.add_source_snapshot("https://mirror.example.com/study", "Mirror")
        lineage = self.service.link_lineage(
            "evidence", source_a["source_id"], source_b["source_id"], "mirror", "Republished copy"
        )
        support = self.service.add_evidence(
            "evidence", snapshot_a["snapshot_id"], "supports", "Quality rose by 10%", "Supports the claim",
            source_a["source_id"], claim_id=self.claim["claim_id"], hypothesis_id=self.hypothesis["hypothesis_id"],
            quality={"directness": "high"}, verified=True,
        )
        counter = self.service.add_evidence(
            "evidence", snapshot_b["snapshot_id"], "contradicts", "Replication found no effect",
            "Weakens the hypothesis", source_a["source_id"], hypothesis_id=self.hypothesis["hypothesis_id"],
            limitations="Mirror shares an origin and is not independent",
        )
        state = self.service.get_programme("evidence")
        self.assertEqual({"supports", "contradicts"}, {item["stance"] for item in state["evidence"]})
        self.assertEqual("mirror", lineage["relation_type"])
        self.assertEqual(support["lineage_group"], counter["lineage_group"])

    def test_belief_revision_requires_evidence_and_keeps_prior(self) -> None:
        source, snapshot = self.add_source_snapshot("https://example.com/result", "Result")
        evidence = self.service.add_evidence(
            "evidence", snapshot["snapshot_id"], "supports", "A controlled result", "Raises confidence",
            source["source_id"], hypothesis_id=self.hypothesis["hypothesis_id"], verified=True,
        )
        with self.assertRaises(DomainError):
            self.service.revise_belief("evidence", self.hypothesis["hypothesis_id"], "likely", "No trigger", [])
        revision = self.service.revise_belief(
            "evidence", self.hypothesis["hypothesis_id"], "likely", "Controlled result supports it",
            [evidence["evidence_id"]],
        )
        state = self.service.get_programme("evidence")
        self.assertEqual("uncertain", revision["prior_assessment"])
        self.assertEqual("likely", revision["new_assessment"])
        self.assertEqual("likely", state["hypotheses"][0]["current_assessment"])
        self.assertEqual(1, len(state["belief_revisions"]))

    def test_experiment_requires_explicit_authorization(self) -> None:
        experiment = self.service.create_experiment(
            "evidence", self.hypothesis["hypothesis_id"], "Run a synthetic comparison",
            "PGRA score exceeds baseline", {"max_runs": 1}, "Stop after one run",
        )
        with self.assertRaises(DomainError):
            self.service.complete_experiment("evidence", experiment["experiment_id"], "completed", {"score": 1})
        self.service.authorize_experiment("evidence", experiment["experiment_id"], True, "Synthetic and bounded")
        completed = self.service.complete_experiment(
            "evidence", experiment["experiment_id"], "inconclusive", {"reason": "tie"}
        )
        self.assertEqual("inconclusive", completed["status"])


if __name__ == "__main__":
    unittest.main()
