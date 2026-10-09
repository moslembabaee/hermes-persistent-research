# Hermes Persistent General Research Agent (PGRA)

PGRA is a design and implementation handoff for a persistent general research agent built on [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent), with [AlekseiUL/hermes-researcher-agent](https://github.com/AlekseiUL/hermes-researcher-agent) used as a reference for privacy-safe public-source research, evidence grading, source-lineage checks, counterexample search, and reproducible research artifacts.

The central idea is simple: a **research programme is a durable, inspectable unit of work**. It is not a long chat transcript. A programme owns questions, hypotheses, evidence and provenance, counterevidence, experiments, belief revisions, open uncertainties, budgets, checkpoints, and an event history. Conversations may start or inspect work, but they are not the system of record.

This repository is currently a **design and handoff package**, not a production implementation. It intentionally avoids claiming Hermes APIs or installation commands that have not been verified against the target Hermes version.

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

Design complete for implementation handoff. Runtime behavior, Hermes integration commands, cross-session persistence, and evaluation results remain to be implemented and verified on the target installation.

## Upstream references

- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- [AlekseiUL/hermes-researcher-agent](https://github.com/AlekseiUL/hermes-researcher-agent)

Upstream projects evolve. Before implementation, record the tested commit/version and inspect the actual CLI rather than copying commands from this document as if they were stable APIs.
