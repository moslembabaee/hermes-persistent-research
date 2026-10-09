# Hermes Persistent General Research Agent (PGRA)

PGRA is a design and implementation handoff for a persistent general research agent built on [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent), with [AlekseiUL/hermes-researcher-agent](https://github.com/AlekseiUL/hermes-researcher-agent) used as a reference for privacy-safe public-source research, evidence grading, source-lineage checks, counterexample search, and reproducible research artifacts.

The central idea is simple: a **research programme is a durable, inspectable unit of work**. It is not a long chat transcript. A programme owns questions, hypotheses, evidence and provenance, counterevidence, experiments, belief revisions, open uncertainties, budgets, checkpoints, and an event history. Conversations may start or inspect work, but they are not the system of record.

This repository is an **installable Hermes PGRA MVP plus a design and implementation handoff**. Version `0.2.0` ships a standard-library Python runtime with SQLite migrations, an append-only event log, programme/cycle/checkpoint CLI, provenance-aware evidence and lineage, explicit belief revision, experiment authorization, paired evaluation, and a real cross-process persistence test.

The MVP persists and audits research state; it does not autonomously browse, schedule itself, or prove research quality. Hermes tools perform collection under user authority, and the PGRA CLI stores the structured results. Scheduling and Hermes chat/user memory are disabled by default so SQLite remains the explicit system of record.

## Install as an independent Hermes profile

The distribution manifest names the profile `pgra`, contains no credentials, ships no cron jobs, and does not target the built-in default profile.

```bash
hermes profile install github.com/moslembabaee/hermes-persistent-research --name pgra --alias
hermes profile show pgra
hermes profile info pgra
hermes -p pgra setup
hermes -p pgra chat
```

Review the install plan before confirming. `setup` is where you configure your own provider and optional tools locally; credentials are never supplied by this repository. If your Hermes release does not have `profile install`, update Hermes and inspect `hermes profile install --help` before proceeding.

For local development from a clone:

```bash
hermes profile install /path/to/hermes-persistent-research --name pgra-dev
hermes -p pgra-dev chat
```

Installation provides `SOUL.md`, safe `config.yaml`, the `pgra-research` skill, design documents, runtime, migrations, CLI, and tests. It never creates a schedule.

## Initialize and verify the runtime

From the installed profile root:

```bash
python pgra.py init
python pgra.py integrity
python -m unittest discover -s tests -p "test_*.py"
```

By default, state is stored at `$HERMES_HOME/pgra/pgra.sqlite3`. You may set `PGRA_DB` or pass `--db` for a specific database. The database and its SQLite sidecars are ignored by Git.

Create and resume a programme:

```bash
python pgra.py programme create \
  --slug vendor-choice \
  --title "Vendor choice" \
  --objective "Choose a vendor using provenance-aware evidence"

python pgra.py cycle start vendor-choice \
  --objective "Collect primary pricing and security evidence" \
  --budget-json '{"max_sources":5,"max_minutes":30}'

python pgra.py programme show vendor-choice
```

Run `python pgra.py --help` for evidence, lineage, hypothesis revision, experiments, checkpoints, status changes, and evaluation commands. See [`docs/CLI_REFERENCE.md`](docs/CLI_REFERENCE.md) for the complete workflow.

### Included runtime capabilities

| Capability | Included in 0.2.0 |
| --- | --- |
| SQLite state engine and checksum-verified migration | Yes |
| Append-only event stream and integrity check | Yes |
| Programme/cycle/checkpoint CLI | Yes |
| Cross-process persistence test | Yes |
| Sources, snapshots, lineage, claims, and evidence | Yes |
| Evidence-triggered belief revision history | Yes |
| Explicitly authorized experiment records | Yes |
| Paired metric evaluation runner | Yes |
| Autonomous web collection | No; Hermes tools collect under user control |
| Cron/background scheduling | No; deliberately absent |

## Design commitments

- SQLite is the first system of record, with an append-only event log and rebuildable projections.
- Every important claim has traceable evidence and source lineage; copied reports do not become independent confirmation.
- Counterevidence and disconfirming tests are first-class objects.
- Beliefs change through explicit revisions, never by silently overwriting an earlier assessment.
- Experiments are bounded by objective, budget, permissions, stop conditions, and expected outputs.
- Persistence works across process and conversation boundaries without relying on chat history.
- Autonomous cycles are bounded. Scheduling is disabled unless the user explicitly opts in.
- The Hermes default profile is never modified. PGRA lives in a separate profile named `pgra`.
- Secrets, credentials, private memories, sessions, cookies, local databases, and private research state must never enter this public repository.
- Quality is measured against a one-shot baseline, including factual quality, calibration, provenance, counterevidence, durability, cost, and time.

## Repository map

| File | Purpose |
| --- | --- |
| [`docs/PGRA_DESIGN.md`](docs/PGRA_DESIGN.md) | Full product and technical design, domain model, persistence model, safety model, and evaluation strategy |
| [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) | Ordered delivery plan beginning with the SQLite Research State Engine |
| [`docs/HERMES_DEFAULT_PROMPT.md`](docs/HERMES_DEFAULT_PROMPT.md) | Paste-ready prompt for handing implementation to Hermes safely |
| [`docs/HANDOFF_BRIEF.md`](docs/HANDOFF_BRIEF.md) | Self-contained handoff summary with phases and acceptance tests |
| [`AGENTS.md`](AGENTS.md) | Non-negotiable rules for coding agents and maintainers |

## Intended operator flow

1. Install or identify the target Hermes Agent version.
2. Read this entire repository and inspect the actual CLI, profile layout, extension points, and security behavior.
3. Propose a version-specific plan and request approval for risky or destructive operations.
4. Create an isolated `pgra` profile without changing the default profile.
5. Implement the state engine and tests before adding autonomous behavior.
6. Run a programme manually and prove that another process or session can resume it from SQLite.
7. Evaluate the persistent run against the same task executed as a one-shot baseline.
8. Enable a scheduler only after explicit user opt-in and only with bounded budgets and a kill switch.

## Non-goals

PGRA is not:

- a hidden always-on daemon;
- an excuse to scrape private or login-gated data;
- a replacement for primary sources or human judgment;
- a system that treats model confidence as evidence;
- a memory dump of every conversation;
- an unbounded recursive agent loop;
- a modification of the user's existing Hermes default profile;
- a repository for credentials or private research data.

## Current status

Profile packaging and isolated sandbox installation are verified against Hermes Agent `v0.21.6`. Runtime unit tests and a real two-process persistence test are included. The MVP does not yet include autonomous Hermes tool adapters, projection rebuild/repair, a scheduler, or published real-world benchmark results.

Run the repository audit locally:

```bash
python scripts/audit_public_distribution.py
python -m unittest discover -s scripts -p "test_*.py"
python -m unittest discover -s tests -p "test_*.py"
```

## Upstream references

- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- [AlekseiUL/hermes-researcher-agent](https://github.com/AlekseiUL/hermes-researcher-agent)

Upstream projects evolve. Before implementation, record the tested commit/version and inspect the actual CLI rather than copying commands from this document as if they were stable APIs.
