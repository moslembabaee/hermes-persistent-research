from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import platform
from pathlib import Path

from . import __version__
from .db import Database, MigrationError
from .service import DomainError, ResearchService


def default_db_path() -> Path:
    explicit = os.environ.get("PGRA_DB", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    profile_root = Path(__file__).resolve().parents[2]
    return profile_root / ".pgra" / "pgra.sqlite3"


def json_file(path: str) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DomainError(f"Cannot read JSON file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DomainError(f"JSON file must contain an object: {path}")
    return value


def output(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pgra", description="Persistent General Research Agent state CLI")
    parser.add_argument("--version", action="version", version=f"PGRA {__version__}")
    parser.add_argument("--db", type=Path, default=default_db_path(), help="SQLite path (default: profile-local PGRA state)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Apply migrations and initialize the state engine")
    sub.add_parser("integrity", help="Run SQLite, foreign-key, and event-stream integrity checks")
    sub.add_parser("doctor", help="Check runtime, database, projection, and scheduler-safe defaults")

    projection = sub.add_parser("projection", help="Compare or rebuild event-derived projections")
    projection_sub = projection.add_subparsers(dest="projection_action", required=True)
    projection_sub.add_parser("status")
    rebuild = projection_sub.add_parser("rebuild")
    rebuild.add_argument("programme")

    backup = sub.add_parser("backup", help="Create or restore a consistent SQLite backup")
    backup_sub = backup.add_subparsers(dest="backup_action", required=True)
    backup_create = backup_sub.add_parser("create")
    backup_create.add_argument("destination", type=Path)
    backup_restore = backup_sub.add_parser("restore")
    backup_restore.add_argument("source", type=Path)
    backup_restore.add_argument("--confirm-restore", action="store_true", required=True)

    programme = sub.add_parser("programme", help="Create and manage research programmes")
    programme_sub = programme.add_subparsers(dest="programme_action", required=True)
    create = programme_sub.add_parser("create")
    create.add_argument("--slug", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--objective", required=True)
    create.add_argument("--policy-json", default="{}")
    create.add_argument("--budget-json", default="{}")
    programme_sub.add_parser("list")
    show = programme_sub.add_parser("show")
    show.add_argument("programme")
    summary = programme_sub.add_parser("summary")
    summary.add_argument("programme")
    report = programme_sub.add_parser("report")
    report.add_argument("programme")
    report.add_argument("--output", type=Path, required=True)
    export = programme_sub.add_parser("export")
    export.add_argument("programme")
    export.add_argument("--output", type=Path, required=True)
    for action in ("pause", "resume", "complete", "cancel", "archive"):
        status_parser = programme_sub.add_parser(action)
        status_parser.add_argument("programme")
        status_parser.add_argument("--reason", required=True)

    hypothesis = sub.add_parser("hypothesis")
    hypothesis_sub = hypothesis.add_subparsers(dest="hypothesis_action", required=True)
    hypothesis_add = hypothesis_sub.add_parser("add")
    hypothesis_add.add_argument("programme")
    hypothesis_add.add_argument("--statement", required=True)
    hypothesis_add.add_argument("--assessment", required=True)
    hypothesis_add.add_argument("--falsifier", required=True)
    hypothesis_list = hypothesis_sub.add_parser("list")
    hypothesis_list.add_argument("programme")
    revise = hypothesis_sub.add_parser("revise")
    revise.add_argument("programme")
    revise.add_argument("hypothesis_id")
    revise.add_argument("--assessment", required=True)
    revise.add_argument("--reasoning", required=True)
    revise.add_argument("--evidence", nargs="+", required=True)

    claim = sub.add_parser("claim")
    claim_sub = claim.add_subparsers(dest="claim_action", required=True)
    claim_add = claim_sub.add_parser("add")
    claim_add.add_argument("programme")
    claim_add.add_argument("--statement", required=True)
    claim_list = claim_sub.add_parser("list")
    claim_list.add_argument("programme")

    source = sub.add_parser("source")
    source_sub = source.add_subparsers(dest="source_action", required=True)
    source_add = source_sub.add_parser("add")
    source_add.add_argument("programme")
    source_add.add_argument("--uri", required=True)
    source_add.add_argument("--title", required=True)
    source_add.add_argument("--type", required=True)
    source_add.add_argument("--publisher")
    source_list = source_sub.add_parser("list")
    source_list.add_argument("programme")
    snapshot = source_sub.add_parser("snapshot")
    snapshot.add_argument("programme")
    snapshot.add_argument("source_id")
    snapshot.add_argument("--observed-uri", required=True)
    snapshot.add_argument("--published-at")
    snapshot.add_argument("--content-hash")
    snapshot.add_argument("--locator")
    snapshot.add_argument("--access-status", default="available")
    snapshot.add_argument("--metadata-json", default="{}")
    snapshot.add_argument("--excerpt")
    snapshot.add_argument("--artifact-path")
    snapshot.add_argument("--access-method", default="manual")
    snapshot.add_argument("--transformations-json", default="{}")

    lineage = sub.add_parser("lineage")
    lineage_sub = lineage.add_subparsers(dest="lineage_action", required=True)
    lineage_link = lineage_sub.add_parser("link")
    lineage_link.add_argument("programme")
    lineage_link.add_argument("parent_source_id")
    lineage_link.add_argument("child_source_id")
    lineage_link.add_argument("--relation", required=True)
    lineage_link.add_argument("--rationale", required=True)

    evidence = sub.add_parser("evidence")
    evidence_sub = evidence.add_subparsers(dest="evidence_action", required=True)
    evidence_add = evidence_sub.add_parser("add")
    evidence_add.add_argument("programme")
    evidence_add.add_argument("--snapshot", required=True)
    evidence_add.add_argument("--claim")
    evidence_add.add_argument("--hypothesis")
    evidence_add.add_argument("--stance", required=True, choices=["supports", "contradicts", "contextualizes", "inconclusive"])
    evidence_add.add_argument("--observation", required=True)
    evidence_add.add_argument("--interpretation", required=True)
    evidence_add.add_argument("--lineage-group", required=True)
    evidence_add.add_argument("--quality-json", default="{}")
    evidence_add.add_argument("--verified", action="store_true")
    evidence_add.add_argument("--limitations", default="")
    evidence_list = evidence_sub.add_parser("list")
    evidence_list.add_argument("programme")

    experiment = sub.add_parser("experiment")
    experiment_sub = experiment.add_subparsers(dest="experiment_action", required=True)
    experiment_add = experiment_sub.add_parser("add")
    experiment_add.add_argument("programme")
    experiment_add.add_argument("hypothesis_id")
    experiment_add.add_argument("--protocol", required=True)
    experiment_add.add_argument("--expected-observation", required=True)
    experiment_add.add_argument("--budget-json", default="{}")
    experiment_add.add_argument("--stop-conditions", required=True)
    authorize = experiment_sub.add_parser("authorize")
    authorize.add_argument("programme")
    authorize.add_argument("experiment_id")
    decision = authorize.add_mutually_exclusive_group(required=True)
    decision.add_argument("--approve", action="store_true")
    decision.add_argument("--deny", action="store_true")
    authorize.add_argument("--reason", required=True)
    finish = experiment_sub.add_parser("finish")
    finish.add_argument("programme")
    finish.add_argument("experiment_id")
    finish.add_argument("--status", required=True, choices=["completed", "failed", "inconclusive"])
    finish.add_argument("--result-json", default="{}")
    experiment_list = experiment_sub.add_parser("list")
    experiment_list.add_argument("programme")

    cycle = sub.add_parser("cycle")
    cycle_sub = cycle.add_subparsers(dest="cycle_action", required=True)
    cycle_start = cycle_sub.add_parser("start")
    cycle_start.add_argument("programme")
    cycle_start.add_argument("--objective", required=True)
    cycle_start.add_argument("--budget-json", default="{}")
    cycle_start.add_argument("--stop-conditions", default="Manual checkpoint required")
    checkpoint = cycle_sub.add_parser("checkpoint")
    checkpoint.add_argument("programme")
    checkpoint.add_argument("--cycle")
    checkpoint.add_argument("--summary-json", required=True)
    checkpoint.add_argument("--status", default="completed", choices=["completed", "paused", "blocked", "exhausted", "failed", "cancelled"])
    checkpoint.add_argument("--reason", default="checkpoint committed")

    evaluation = sub.add_parser("evaluation")
    evaluation_sub = evaluation.add_subparsers(dest="evaluation_action", required=True)
    template = evaluation_sub.add_parser("template")
    template.add_argument("--directory", type=Path, required=True)
    compare = evaluation_sub.add_parser("compare")
    compare.add_argument("--programme")
    compare.add_argument("--name", required=True)
    compare.add_argument("--baseline", required=True)
    compare.add_argument("--pgra", required=True)

    return parser


def dispatch(args: argparse.Namespace):
    database = Database(args.db)
    if args.command == "init":
        database.migrate()
        return {"ok": True, "database": str(database.path), "message": "PGRA state engine initialized"}
    if args.command == "integrity":
        return database.integrity()
    if args.command == "doctor":
        integrity = database.integrity()
        return {
            "ok": integrity["ok"] and sys.version_info >= (3, 10),
            "pgra_version": __version__,
            "python": platform.python_version(),
            "python_supported": sys.version_info >= (3, 10),
            "database": str(database.path),
            "integrity": integrity,
            "scheduler": "absent (safe default)",
            "hermes_profile": os.environ.get("HERMES_PROFILE", "not reported by environment"),
        }
    if args.command == "projection":
        if args.projection_action == "status":
            return database.projection_status()
        return database.rebuild_projection(args.programme)
    if args.command == "backup":
        if args.backup_action == "create":
            return database.backup(args.destination)
        return database.restore(args.source)
    service = ResearchService(database)

    if args.command == "programme":
        if args.programme_action == "create":
            return service.create_programme(args.slug, args.title, args.objective, args.policy_json, args.budget_json)
        if args.programme_action == "list":
            return service.list_programmes()
        if args.programme_action == "show":
            return service.get_programme(args.programme)
        if args.programme_action == "summary":
            return service.programme_summary(args.programme)
        if args.programme_action == "report":
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(service.markdown_report(args.programme), encoding="utf-8")
            return {"ok": True, "output": str(args.output.resolve()), "format": "markdown"}
        if args.programme_action == "export":
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(service.sanitized_export(args.programme), ensure_ascii=False, indent=2), encoding="utf-8")
            return {"ok": True, "output": str(args.output.resolve()), "sanitized": True}
        status = {"pause": "paused", "resume": "active", "complete": "completed", "cancel": "cancelled", "archive": "archived"}[args.programme_action]
        return service.set_programme_status(args.programme, status, args.reason)
    if args.command == "hypothesis":
        if args.hypothesis_action == "list":
            return service.list_entities(args.programme, "hypotheses")
        if args.hypothesis_action == "add":
            return service.add_hypothesis(args.programme, args.statement, args.assessment, args.falsifier)
        return service.revise_belief(args.programme, args.hypothesis_id, args.assessment, args.reasoning, args.evidence)
    if args.command == "claim":
        if args.claim_action == "list":
            return service.list_entities(args.programme, "claims")
        return service.add_claim(args.programme, args.statement)
    if args.command == "source":
        if args.source_action == "list":
            return service.list_entities(args.programme, "sources")
        if args.source_action == "add":
            return service.add_source(args.programme, args.uri, args.title, args.type, args.publisher)
        return service.add_snapshot(args.programme, args.source_id, args.observed_uri, published_at=args.published_at,
                                    content_hash=args.content_hash, locator=args.locator,
                                    access_status=args.access_status, metadata=args.metadata_json,
                                    excerpt=args.excerpt, artifact_path=args.artifact_path,
                                    access_method=args.access_method, transformations=args.transformations_json)
    if args.command == "lineage":
        return service.link_lineage(args.programme, args.parent_source_id, args.child_source_id, args.relation, args.rationale)
    if args.command == "evidence":
        if args.evidence_action == "list":
            return service.list_entities(args.programme, "evidence")
        return service.add_evidence(args.programme, args.snapshot, args.stance, args.observation,
                                    args.interpretation, args.lineage_group, claim_id=args.claim,
                                    hypothesis_id=args.hypothesis, quality=args.quality_json,
                                    verified=args.verified, limitations=args.limitations)
    if args.command == "experiment":
        if args.experiment_action == "list":
            return service.list_entities(args.programme, "experiments")
        if args.experiment_action == "add":
            return service.create_experiment(args.programme, args.hypothesis_id, args.protocol,
                                             args.expected_observation, args.budget_json, args.stop_conditions)
        if args.experiment_action == "authorize":
            return service.authorize_experiment(args.programme, args.experiment_id, args.approve, args.reason)
        return service.complete_experiment(args.programme, args.experiment_id, args.status, args.result_json)
    if args.command == "cycle":
        if args.cycle_action == "start":
            return service.start_cycle(args.programme, args.objective, args.budget_json, args.stop_conditions)
        return service.checkpoint(args.programme, args.summary_json, args.cycle, args.status, args.reason)
    if args.command == "evaluation":
        if args.evaluation_action == "template":
            args.directory.mkdir(parents=True, exist_ok=True)
            template = {
                "metrics": {
                    "factual_correctness": 0.0,
                    "citation_entailment": 0.0,
                    "provenance_completeness": 0.0,
                    "lineage_accuracy": 0.0,
                    "counterevidence_coverage": 0.0,
                    "calibration": 0.0,
                    "continuity": 0.0,
                    "reproducibility": 0.0,
                    "safety": 0.0,
                    "decision_usefulness": 0.0,
                },
                "conditions": {"model": "record-model", "budget": "record-comparable-budget"},
                "cost": {"usd": 0.0, "seconds": 0, "tool_calls": 0},
                "limitations": ["Replace this template with independently reviewed scores and limitations."],
            }
            for name in ("baseline.json", "pgra.json"):
                (args.directory / name).write_text(json.dumps(template, indent=2), encoding="utf-8")
            rubric = args.directory / "RUBRIC.md"
            rubric.write_text(
                "# Paired evaluation rubric\n\nScore each metric from 0 to 1 using the same reviewer and evidence standard. "
                "Keep model, tools, source access, evidence policy, and total budget comparable. Record every mismatch and limitation.\n",
                encoding="utf-8",
            )
            return {"ok": True, "directory": str(args.directory.resolve()), "files": ["baseline.json", "pgra.json", "RUBRIC.md"]}
        return service.record_evaluation(args.programme, args.name, json_file(args.baseline), json_file(args.pgra))
    raise DomainError(f"Unsupported command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = dispatch(args)
        output(result)
        return 0 if not isinstance(result, dict) or result.get("ok", True) else 1
    except (DomainError, MigrationError, sqlite3.Error, ValueError) as exc:  # type: ignore[name-defined]
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
