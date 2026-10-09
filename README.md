# Hermes Persistent General Research Agent (PGRA)

[![Profile distribution quality](https://github.com/moslembabaee/hermes-persistent-research/actions/workflows/profile-distribution.yml/badge.svg)](https://github.com/moslembabaee/hermes-persistent-research/actions/workflows/profile-distribution.yml)

PGRA is an installable, isolated [Hermes Agent](https://github.com/NousResearch/hermes-agent) profile for research that must survive beyond one chat. Its durable unit is a **research programme** containing hypotheses, claims, source snapshots, evidence and counterevidence, experiments, belief revisions, bounded cycles, checkpoints, and evaluations.

Version `0.3.0` is a local-first MVP. SQLite is the only required state service. PGRA does not install a scheduler, modify the Hermes default profile, or require Obsidian, Hindsight, PostgreSQL, or a vector database.

## What is implemented

- checksum-verified SQLite migrations and foreign-key enforcement;
- append-only events with a complete projection snapshot for drift detection and repair;
- programme, hypothesis, claim, source, evidence, lineage, experiment, cycle, and checkpoint commands;
- verifiable source snapshots with required locator and SHA-256 hash for available content;
- explicit, evidence-triggered belief revision history;
- programme and cycle count budgets for sources, evidence, experiments, and cycles;
- valid programme and experiment lifecycle transitions;
- human-readable summaries and Markdown reports;
- sanitized JSON export and SQLite-safe backup/restore;
- normalized paired evaluation comparison and starter rubric;
- real cross-process persistence tests.

Hermes integration is currently **instruction-driven**: the bundled profile and skill tell Hermes how to call the PGRA CLI. There is not yet an automatic hook that records every Hermes action. The CLI and SQLite database remain authoritative.

## Requirements

- Hermes Agent `0.21.6` or newer;
- Python `3.10` or newer;
- Git for URL-based profile installation.

The runtime uses only the Python standard library.

## Install the isolated profile

```text
hermes profile install github.com/moslembabaee/hermes-persistent-research --name pgra --alias
hermes profile show pgra
hermes profile info pgra
hermes -p pgra setup
```

The install preview should show profile name `pgra` and no cron payload. `setup` configures your own model provider locally. This repository contains no credentials.

Start Hermes with the isolated profile:

```text
hermes -p pgra chat
```

## First successful programme

Use `hermes profile info pgra` to locate the installed profile directory, change into that directory, then run the following commands. Every command below is a single line and works in PowerShell, Command Prompt, Bash, and zsh.

```text
python pgra.py doctor
python pgra.py init
python pgra.py programme create --slug vendor-choice --title "Vendor choice" --objective "Choose a vendor using provenance-aware evidence"
python pgra.py cycle start vendor-choice --objective "Collect primary pricing and security evidence" --stop-conditions "Stop after five sources or a material access barrier"
python pgra.py programme summary vendor-choice
```

For budget and policy JSON, single-quoted JSON works in PowerShell, Bash, and zsh. Command Prompt has different quoting rules; use a PowerShell terminal on Windows for those arguments. For complex policies, constructing JSON with `ConvertTo-Json` is safer. You may also avoid shell quoting by invoking the commands from Hermes chat through the bundled skill.

State defaults to `.pgra/pgra.sqlite3` inside the installed PGRA profile, derived from the runtime location rather than the process working directory or global Hermes home. This keeps multiple profiles isolated. Override it with `PGRA_DB` or the global `--db PATH` option.

## Capture evidence

An available source snapshot requires an exact locator and a SHA-256 content hash. A short excerpt or a local artifact path may also be recorded; local artifacts remain private and are removed from sanitized exports.

```text
python pgra.py source add vendor-choice --uri https://example.com/report --title "Primary report" --type primary
python pgra.py source snapshot vendor-choice SOURCE_ID --observed-uri https://example.com/report --locator "section 2" --content-hash SHA256_HEX --access-method browser --excerpt "Short permitted excerpt"
python pgra.py evidence add vendor-choice --snapshot SNAPSHOT_ID --hypothesis HYPOTHESIS_ID --stance supports --observation "Observed fact" --interpretation "Why it matters" --lineage-group ORIGINAL_SOURCE_ID --verified
```

Use IDs returned by the CLI; do not guess them. See [the complete CLI reference](docs/CLI_REFERENCE.md).

## Inspect, report, and export

```text
python pgra.py programme summary vendor-choice
python pgra.py hypothesis list vendor-choice
python pgra.py evidence list vendor-choice
python pgra.py programme report vendor-choice --output .pgra/exports/report.md
python pgra.py programme export vendor-choice --output .pgra/exports/export.json
python pgra.py integrity
python pgra.py projection status
```

`programme export` is deliberately sanitized: it omits event payloads and local artifact paths. It is not a substitute for reviewing the output before publishing it.

## Backup and recovery

Never copy a live SQLite file directly. Use SQLite's online backup API through the CLI:

```text
python pgra.py backup create .pgra/backups/pgra-2026-10-09.sqlite3
python pgra.py backup restore .pgra/backups/pgra-2026-10-09.sqlite3 --confirm-restore
```

Restore validates the source and creates a `.before-restore` safety backup of the current database. See [backup and recovery](docs/BACKUP_AND_RECOVERY.md).

## Paired evaluation

Generate comparable input templates and a rubric:

```text
python pgra.py evaluation template --directory .pgra/evaluation-case
python pgra.py evaluation compare --programme vendor-choice --name vendor-choice-v1 --baseline .pgra/evaluation-case/baseline.json --pgra .pgra/evaluation-case/pgra.json
```

Scores must be between 0 and 1 and use identical metric keys. The comparator does not invent scores or claim causality; reviewers must record conditions, costs, evidence, and limitations.

## Verify the installation

```text
python scripts/audit_public_distribution.py
python -m unittest discover -s scripts -p "test_*.py"
python -W error::ResourceWarning -m unittest discover -s tests -p "test_*.py"
```

## Safety defaults

- The Hermes default profile is never a target.
- No cron job, scheduled task, watcher, or service is shipped.
- SQLite is the explicit system of record; Hermes chat memory is disabled in this profile.
- Secrets, sessions, cookies, local databases, artifacts, exports, and private research state are ignored by Git.
- Experiments require explicit authorization and cannot be completed twice.
- Completed or cancelled programmes cannot silently become active again.

## Known limitations

- Hermes tool actions are not automatically captured; Hermes must intentionally call the CLI.
- Budgets are enforced for stored cycles, sources, evidence, and experiments, but model tokens, wall time, bytes, tool calls, and monetary cost are not yet metered by a live Hermes adapter.
- Projection snapshots make rebuild and drift repair reliable but increase event-log size; a compact reducer is future work.
- Source excerpts and artifact references are supported, but PGRA is not a web archiver.
- The evaluation component validates and compares reviewer-provided measurements; it does not run models or grade answers automatically.
- Command-level idempotency keys, leases, a meta-controller, and opt-in scheduling are not implemented.

## Repository guide

- [Complete design](docs/PGRA_DESIGN.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)
- [Consumer hardening plan](docs/CONSUMER_HARDENING_PLAN.md)
- [Self-contained handoff](docs/HANDOFF_BRIEF.md)
- [Hermes implementation prompt](docs/HERMES_DEFAULT_PROMPT.md)
- [CLI reference](docs/CLI_REFERENCE.md)
- [Changelog](CHANGELOG.md)

The public package is available under the [MIT License](LICENSE). Upstream references are [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) and [AlekseiUL/hermes-researcher-agent](https://github.com/AlekseiUL/hermes-researcher-agent).
