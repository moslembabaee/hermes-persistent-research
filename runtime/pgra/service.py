from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .db import Database
from .evaluation import compare_runs


class DomainError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def parse_json_object(value: str | dict | None, field: str) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise DomainError(f"{field} must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise DomainError(f"{field} must be a JSON object")
    return parsed


def canonical_uri(uri: str) -> str:
    uri = uri.strip()
    parts = urlsplit(uri)
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
        raise DomainError("Source URI must be an absolute public http(s) URI")
    host = parts.netloc.lower()
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), host, path.rstrip("/") or "/", parts.query, ""))


def row_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


class ResearchService:
    def __init__(self, database: Database):
        self.db = database
        self.db.migrate()

    def _programme(self, connection: sqlite3.Connection, identifier: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM programmes WHERE programme_id=? OR slug=?", (identifier, identifier)
        ).fetchone()
        if row is None:
            raise DomainError(f"Programme not found: {identifier}")
        return row

    def _owned(self, connection: sqlite3.Connection, table: str, id_column: str, entity_id: str, programme_id: str):
        allowed = {
            ("hypotheses", "hypothesis_id"), ("claims", "claim_id"), ("sources", "source_id"),
            ("source_snapshots", "snapshot_id"), ("research_cycles", "cycle_id"),
            ("experiments", "experiment_id"),
        }
        if (table, id_column) not in allowed:
            raise DomainError("Invalid ownership query")
        if table == "source_snapshots":
            row = connection.execute(
                """SELECT ss.* FROM source_snapshots ss JOIN sources s ON s.source_id=ss.source_id
                   WHERE ss.snapshot_id=? AND s.programme_id=?""", (entity_id, programme_id)
            ).fetchone()
        else:
            row = connection.execute(
                f"SELECT * FROM {table} WHERE {id_column}=? AND programme_id=?", (entity_id, programme_id)
            ).fetchone()
        if row is None:
            raise DomainError(f"{id_column} not found in programme: {entity_id}")
        return row

    def _event_by_key(self, connection: sqlite3.Connection, programme_id: str, key: str | None):
        if not key:
            return None
        return connection.execute(
            "SELECT * FROM events WHERE programme_id=? AND idempotency_key=?", (programme_id, key)
        ).fetchone()

    def _append_event(
        self,
        connection: sqlite3.Connection,
        programme_id: str,
        event_type: str,
        payload: dict,
        *,
        actor: str = "user",
        idempotency_key: str | None = None,
        causation_id: str | None = None,
        correlation_id: str | None = None,
    ) -> dict:
        previous = self._event_by_key(connection, programme_id, idempotency_key)
        if previous:
            return dict(previous)
        programme = self._programme(connection, programme_id)
        version = programme["version"] + 1
        payload_json = canonical_json(payload)
        event = {
            "event_id": new_id("evt"),
            "programme_id": programme["programme_id"],
            "stream_version": version,
            "event_type": event_type,
            "occurred_at": utc_now(),
            "actor": actor,
            "causation_id": causation_id,
            "correlation_id": correlation_id,
            "idempotency_key": idempotency_key,
            "schema_version": 1,
            "payload_json": payload_json,
            "payload_hash": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        }
        connection.execute(
            """INSERT INTO events(event_id,programme_id,stream_version,event_type,occurred_at,actor,
               causation_id,correlation_id,idempotency_key,schema_version,payload_json,payload_hash)
               VALUES(:event_id,:programme_id,:stream_version,:event_type,:occurred_at,:actor,
               :causation_id,:correlation_id,:idempotency_key,:schema_version,:payload_json,:payload_hash)""",
            event,
        )
        connection.execute(
            "UPDATE programmes SET version=?, updated_at=? WHERE programme_id=? AND version=?",
            (version, event["occurred_at"], programme["programme_id"], programme["version"]),
        )
        if connection.execute("SELECT changes()").fetchone()[0] != 1:
            raise DomainError("Concurrent programme update detected")
        return event

    def create_programme(self, slug: str, title: str, objective: str, policy=None, budget=None) -> dict:
        slug = slug.strip().lower()
        if not slug or not all(char.isalnum() or char == "-" for char in slug):
            raise DomainError("Slug must contain lowercase letters, numbers, or hyphens")
        now = utc_now()
        programme_id = new_id("prg")
        policy_obj = parse_json_object(policy, "policy")
        budget_obj = parse_json_object(budget, "budget")
        with self.db.transaction() as connection:
            try:
                connection.execute(
                    """INSERT INTO programmes(programme_id,slug,title,objective,status,policy_json,budget_json,version,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (programme_id, slug, title.strip(), objective.strip(), "active", canonical_json(policy_obj),
                     canonical_json(budget_obj), 0, now, now),
                )
            except sqlite3.IntegrityError as exc:
                raise DomainError(f"Programme slug already exists: {slug}") from exc
            self._append_event(connection, programme_id, "ProgrammeCreated", {
                "programme_id": programme_id, "slug": slug, "title": title.strip(),
                "objective": objective.strip(), "policy": policy_obj, "budget": budget_obj,
            })
            return dict(self._programme(connection, programme_id))

    def list_programmes(self) -> list[dict]:
        with self.db.session() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM programmes ORDER BY created_at")]

    def get_programme(self, identifier: str) -> dict:
        with self.db.session() as connection:
            programme = dict(self._programme(connection, identifier))
            pid = programme["programme_id"]
            programme["policy"] = json.loads(programme.pop("policy_json"))
            programme["budget"] = json.loads(programme.pop("budget_json"))
            for name, query in {
                "hypotheses": "SELECT * FROM hypotheses WHERE programme_id=? ORDER BY created_at",
                "claims": "SELECT * FROM claims WHERE programme_id=? ORDER BY created_at",
                "sources": "SELECT * FROM sources WHERE programme_id=? ORDER BY created_at",
                "source_snapshots": """SELECT ss.* FROM source_snapshots ss JOIN sources s ON s.source_id=ss.source_id
                                      WHERE s.programme_id=? ORDER BY ss.retrieved_at""",
                "source_lineage": "SELECT * FROM source_lineage WHERE programme_id=? ORDER BY created_at",
                "evidence": "SELECT * FROM evidence_items WHERE programme_id=? ORDER BY created_at",
                "belief_revisions": "SELECT * FROM belief_revisions WHERE programme_id=? ORDER BY created_at",
                "experiments": "SELECT * FROM experiments WHERE programme_id=? ORDER BY created_at",
                "cycles": "SELECT * FROM research_cycles WHERE programme_id=? ORDER BY started_at",
                "checkpoints": "SELECT * FROM checkpoints WHERE programme_id=? ORDER BY created_at",
                "evaluations": "SELECT * FROM evaluation_runs WHERE programme_id=? ORDER BY created_at",
                "events": "SELECT * FROM events WHERE programme_id=? ORDER BY stream_version",
            }.items():
                programme[name] = [dict(row) for row in connection.execute(query, (pid,))]
            return programme

    def set_programme_status(self, identifier: str, status: str, reason: str) -> dict:
        allowed = {"active", "paused", "blocked", "completed", "cancelled", "archived"}
        if status not in allowed:
            raise DomainError(f"Invalid programme status: {status}")
        with self.db.transaction() as connection:
            programme = self._programme(connection, identifier)
            connection.execute("UPDATE programmes SET status=? WHERE programme_id=?", (status, programme["programme_id"]))
            self._append_event(connection, programme["programme_id"], "ProgrammeStatusChanged", {
                "from": programme["status"], "to": status, "reason": reason,
            })
            return dict(self._programme(connection, programme["programme_id"]))

    def add_hypothesis(self, identifier: str, statement: str, assessment: str, falsifier: str) -> dict:
        now = utc_now()
        hypothesis_id = new_id("hyp")
        with self.db.transaction() as connection:
            programme = self._programme(connection, identifier)
            connection.execute(
                "INSERT INTO hypotheses VALUES(?,?,?,?,?,?,?,?)",
                (hypothesis_id, programme["programme_id"], statement, falsifier, "active", assessment, now, now),
            )
            self._append_event(connection, programme["programme_id"], "HypothesisProposed", {
                "hypothesis_id": hypothesis_id, "statement": statement,
                "assessment": assessment, "falsifier": falsifier,
            })
            return dict(self._owned(connection, "hypotheses", "hypothesis_id", hypothesis_id, programme["programme_id"]))

    def add_claim(self, identifier: str, statement: str) -> dict:
        claim_id, now = new_id("clm"), utc_now()
        with self.db.transaction() as connection:
            programme = self._programme(connection, identifier)
            connection.execute("INSERT INTO claims VALUES(?,?,?,?)", (claim_id, programme["programme_id"], statement, now))
            self._append_event(connection, programme["programme_id"], "ClaimAdded", {"claim_id": claim_id, "statement": statement})
            return dict(self._owned(connection, "claims", "claim_id", claim_id, programme["programme_id"]))

    def add_source(self, identifier: str, uri: str, title: str, source_type: str, publisher: str | None = None) -> dict:
        source_id, now = new_id("src"), utc_now()
        normalized = canonical_uri(uri)
        with self.db.transaction() as connection:
            programme = self._programme(connection, identifier)
            try:
                connection.execute("INSERT INTO sources VALUES(?,?,?,?,?,?,?)", (
                    source_id, programme["programme_id"], normalized, title, source_type, publisher, now,
                ))
            except sqlite3.IntegrityError as exc:
                raise DomainError(f"Source already exists in programme: {normalized}") from exc
            self._append_event(connection, programme["programme_id"], "SourceAdded", {
                "source_id": source_id, "canonical_uri": normalized, "title": title, "source_type": source_type,
            })
            return dict(self._owned(connection, "sources", "source_id", source_id, programme["programme_id"]))

    def add_snapshot(self, identifier: str, source_id: str, observed_uri: str, *, published_at=None,
                     content_hash=None, locator=None, access_status="available", metadata=None) -> dict:
        snapshot_id, now = new_id("snp"), utc_now()
        metadata_obj = parse_json_object(metadata, "metadata")
        with self.db.transaction() as connection:
            programme = self._programme(connection, identifier)
            self._owned(connection, "sources", "source_id", source_id, programme["programme_id"])
            connection.execute("INSERT INTO source_snapshots VALUES(?,?,?,?,?,?,?,?,?)", (
                snapshot_id, source_id, canonical_uri(observed_uri), now, published_at, content_hash,
                locator, access_status, canonical_json(metadata_obj),
            ))
            self._append_event(connection, programme["programme_id"], "SourceObserved", {
                "snapshot_id": snapshot_id, "source_id": source_id, "retrieved_at": now,
                "access_status": access_status, "content_hash": content_hash,
            })
            return dict(self._owned(connection, "source_snapshots", "snapshot_id", snapshot_id, programme["programme_id"]))

    def link_lineage(self, identifier: str, parent_source_id: str, child_source_id: str,
                     relation_type: str, rationale: str) -> dict:
        lineage_id, now = new_id("lin"), utc_now()
        with self.db.transaction() as connection:
            programme = self._programme(connection, identifier)
            for source_id in (parent_source_id, child_source_id):
                self._owned(connection, "sources", "source_id", source_id, programme["programme_id"])
            connection.execute("INSERT INTO source_lineage VALUES(?,?,?,?,?,?,?)", (
                lineage_id, programme["programme_id"], parent_source_id, child_source_id,
                relation_type, rationale, now,
            ))
            self._append_event(connection, programme["programme_id"], "LineageLinked", {
                "lineage_id": lineage_id, "parent_source_id": parent_source_id,
                "child_source_id": child_source_id, "relation_type": relation_type,
            })
            return dict(connection.execute("SELECT * FROM source_lineage WHERE lineage_id=?", (lineage_id,)).fetchone())

    def add_evidence(self, identifier: str, snapshot_id: str, stance: str, observation: str,
                     interpretation: str, lineage_group: str, *, claim_id=None, hypothesis_id=None,
                     quality=None, verified=False, limitations="") -> dict:
        if stance not in {"supports", "contradicts", "contextualizes", "inconclusive"}:
            raise DomainError(f"Invalid evidence stance: {stance}")
        if not claim_id and not hypothesis_id:
            raise DomainError("Evidence requires claim_id or hypothesis_id")
        evidence_id, now = new_id("evd"), utc_now()
        quality_obj = parse_json_object(quality, "quality")
        with self.db.transaction() as connection:
            programme = self._programme(connection, identifier)
            pid = programme["programme_id"]
            self._owned(connection, "source_snapshots", "snapshot_id", snapshot_id, pid)
            if claim_id:
                self._owned(connection, "claims", "claim_id", claim_id, pid)
            if hypothesis_id:
                self._owned(connection, "hypotheses", "hypothesis_id", hypothesis_id, pid)
            connection.execute(
                """INSERT INTO evidence_items VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (evidence_id, pid, claim_id, hypothesis_id, snapshot_id, stance, observation,
                 interpretation, canonical_json(quality_obj), lineage_group, int(verified), limitations, now),
            )
            self._append_event(connection, pid, "EvidenceRecorded", {
                "evidence_id": evidence_id, "claim_id": claim_id, "hypothesis_id": hypothesis_id,
                "snapshot_id": snapshot_id, "stance": stance, "lineage_group": lineage_group,
            })
            return dict(connection.execute("SELECT * FROM evidence_items WHERE evidence_id=?", (evidence_id,)).fetchone())

    def revise_belief(self, identifier: str, hypothesis_id: str, new_assessment: str,
                      reasoning: str, evidence_ids: list[str]) -> dict:
        if not evidence_ids:
            raise DomainError("Belief revision requires at least one evidence item")
        revision_id, now = new_id("rev"), utc_now()
        with self.db.transaction() as connection:
            programme = self._programme(connection, identifier)
            pid = programme["programme_id"]
            hypothesis = self._owned(connection, "hypotheses", "hypothesis_id", hypothesis_id, pid)
            placeholders = ",".join("?" for _ in evidence_ids)
            found = connection.execute(
                f"SELECT evidence_id FROM evidence_items WHERE programme_id=? AND evidence_id IN ({placeholders})",
                (pid, *evidence_ids),
            ).fetchall()
            if len(found) != len(set(evidence_ids)):
                raise DomainError("All belief revision evidence must belong to the programme")
            parent = connection.execute(
                "SELECT revision_id FROM belief_revisions WHERE hypothesis_id=? ORDER BY created_at DESC LIMIT 1",
                (hypothesis_id,),
            ).fetchone()
            connection.execute("INSERT INTO belief_revisions VALUES(?,?,?,?,?,?,?,?,?)", (
                revision_id, pid, hypothesis_id, hypothesis["current_assessment"], new_assessment,
                reasoning, canonical_json(sorted(set(evidence_ids))), parent[0] if parent else None, now,
            ))
            connection.execute(
                "UPDATE hypotheses SET current_assessment=?, updated_at=? WHERE hypothesis_id=?",
                (new_assessment, now, hypothesis_id),
            )
            self._append_event(connection, pid, "BeliefRevised", {
                "revision_id": revision_id, "hypothesis_id": hypothesis_id,
                "prior_assessment": hypothesis["current_assessment"], "new_assessment": new_assessment,
                "evidence_ids": sorted(set(evidence_ids)), "reasoning": reasoning,
            })
            return dict(connection.execute("SELECT * FROM belief_revisions WHERE revision_id=?", (revision_id,)).fetchone())

    def create_experiment(self, identifier: str, hypothesis_id: str, protocol: str,
                          expected_observation: str, budget=None, stop_conditions="") -> dict:
        experiment_id, now = new_id("exp"), utc_now()
        budget_obj = parse_json_object(budget, "budget")
        with self.db.transaction() as connection:
            programme = self._programme(connection, identifier)
            pid = programme["programme_id"]
            self._owned(connection, "hypotheses", "hypothesis_id", hypothesis_id, pid)
            connection.execute("INSERT INTO experiments VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (
                experiment_id, pid, hypothesis_id, protocol, expected_observation, "pending",
                canonical_json(budget_obj), stop_conditions, "proposed", None, now, now,
            ))
            self._append_event(connection, pid, "ExperimentProposed", {
                "experiment_id": experiment_id, "hypothesis_id": hypothesis_id,
                "protocol": protocol, "budget": budget_obj, "stop_conditions": stop_conditions,
            })
            return dict(self._owned(connection, "experiments", "experiment_id", experiment_id, pid))

    def authorize_experiment(self, identifier: str, experiment_id: str, approved: bool, reason: str) -> dict:
        now = utc_now()
        with self.db.transaction() as connection:
            programme = self._programme(connection, identifier)
            experiment = self._owned(connection, "experiments", "experiment_id", experiment_id, programme["programme_id"])
            permission = "approved" if approved else "denied"
            status = "authorized" if approved else "cancelled"
            connection.execute(
                "UPDATE experiments SET permission_status=?, status=?, updated_at=? WHERE experiment_id=?",
                (permission, status, now, experiment_id),
            )
            self._append_event(connection, programme["programme_id"], "ExperimentAuthorized" if approved else "ExperimentDenied", {
                "experiment_id": experiment_id, "reason": reason, "prior_status": experiment["status"],
            })
            return dict(self._owned(connection, "experiments", "experiment_id", experiment_id, programme["programme_id"]))

    def complete_experiment(self, identifier: str, experiment_id: str, status: str, result=None) -> dict:
        if status not in {"completed", "failed", "inconclusive"}:
            raise DomainError("Experiment terminal status must be completed, failed, or inconclusive")
        result_obj = parse_json_object(result, "result")
        now = utc_now()
        with self.db.transaction() as connection:
            programme = self._programme(connection, identifier)
            experiment = self._owned(connection, "experiments", "experiment_id", experiment_id, programme["programme_id"])
            if experiment["permission_status"] != "approved":
                raise DomainError("Experiment must be explicitly approved before completion")
            connection.execute(
                "UPDATE experiments SET status=?, result_json=?, updated_at=? WHERE experiment_id=?",
                (status, canonical_json(result_obj), now, experiment_id),
            )
            self._append_event(connection, programme["programme_id"], "ExperimentCompleted", {
                "experiment_id": experiment_id, "status": status, "result": result_obj,
            })
            return dict(self._owned(connection, "experiments", "experiment_id", experiment_id, programme["programme_id"]))

    def start_cycle(self, identifier: str, objective: str, budget=None) -> dict:
        cycle_id, now = new_id("cyc"), utc_now()
        budget_obj = parse_json_object(budget, "budget")
        with self.db.transaction() as connection:
            programme = self._programme(connection, identifier)
            if programme["status"] != "active":
                raise DomainError("Programme must be active to start a cycle")
            try:
                connection.execute("INSERT INTO research_cycles VALUES(?,?,?,?,?,?,?,?,?)", (
                    cycle_id, programme["programme_id"], objective, "running", programme["policy_json"],
                    canonical_json(budget_obj), now, None, None,
                ))
            except sqlite3.IntegrityError as exc:
                raise DomainError("Programme already has a running cycle") from exc
            self._append_event(connection, programme["programme_id"], "CycleStarted", {
                "cycle_id": cycle_id, "objective": objective, "budget": budget_obj,
            })
            return dict(self._owned(connection, "research_cycles", "cycle_id", cycle_id, programme["programme_id"]))

    def checkpoint(self, identifier: str, summary, cycle_id: str | None = None,
                   cycle_status: str = "completed", terminal_reason: str = "checkpoint committed") -> dict:
        if cycle_status not in {"completed", "paused", "blocked", "exhausted", "failed", "cancelled"}:
            raise DomainError("Invalid cycle terminal status")
        summary_obj = parse_json_object(summary, "summary")
        checkpoint_id, now = new_id("chk"), utc_now()
        with self.db.transaction() as connection:
            programme = self._programme(connection, identifier)
            pid = programme["programme_id"]
            if cycle_id:
                cycle = self._owned(connection, "research_cycles", "cycle_id", cycle_id, pid)
                if cycle["status"] != "running":
                    raise DomainError("Only a running cycle can be checkpointed")
                connection.execute(
                    "UPDATE research_cycles SET status=?, ended_at=?, terminal_reason=? WHERE cycle_id=?",
                    (cycle_status, now, terminal_reason, cycle_id),
                )
            event = self._append_event(connection, pid, "CheckpointCreated", {
                "checkpoint_id": checkpoint_id, "cycle_id": cycle_id, "summary": summary_obj,
                "cycle_status": cycle_status, "terminal_reason": terminal_reason,
            })
            connection.execute("INSERT INTO checkpoints VALUES(?,?,?,?,?,?)", (
                checkpoint_id, pid, cycle_id, canonical_json(summary_obj), event["stream_version"], now,
            ))
            return dict(connection.execute("SELECT * FROM checkpoints WHERE checkpoint_id=?", (checkpoint_id,)).fetchone())

    def record_evaluation(self, identifier: str | None, benchmark_name: str, baseline: dict, pgra: dict) -> dict:
        result = compare_runs(baseline, pgra)
        evaluation_id, now = new_id("eva"), utc_now()
        with self.db.transaction() as connection:
            programme_id = None
            if identifier:
                programme_id = self._programme(connection, identifier)["programme_id"]
            connection.execute("INSERT INTO evaluation_runs VALUES(?,?,?,?,?,?,?)", (
                evaluation_id, programme_id, benchmark_name, canonical_json(baseline), canonical_json(pgra),
                canonical_json(result), now,
            ))
            if programme_id:
                self._append_event(connection, programme_id, "EvaluationCompleted", {
                    "evaluation_id": evaluation_id, "benchmark_name": benchmark_name,
                    "summary": result["summary"], "comparable": result["comparable"],
                })
            return {
                "evaluation_id": evaluation_id, "programme_id": programme_id,
                "benchmark_name": benchmark_name, "result": result, "created_at": now,
            }
