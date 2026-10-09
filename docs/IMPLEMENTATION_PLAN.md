# PGRA implementation plan

## Implemented MVP status (0.3.0)

The installable profile now includes the Phase 1 core with projection drift detection/rebuild and SQLite-safe backup/restore, structured Phase 2 evidence storage with verifiable snapshot hashes, Phase 3 belief/experiment records with lifecycle guards, manual Phase 4 cycles/checkpoints with count-budget enforcement, and a Phase 6 paired metric comparator with normalized scores and templates. Cross-process persistence is exercised by an automated test. Remaining hardening includes command-level idempotency on every public operation, live metering of time/tokens/cost/tool calls, live Hermes tool adapters, leases/outbox, meta-controller implementation, real benchmark datasets, and optional scheduling only after explicit opt-in.

The work is ordered so durable state and safety exist before autonomy. Every phase produces reviewable artifacts and must pass its exit gate before later behavior is trusted.

## Phase 1 — SQLite Research State Engine

Build the authoritative local-first state layer before integrating research tools.

### Deliverables

- Select the implementation language/binding after inspecting the actual Hermes version and extension options.
- Establish package layout, dependency locking, formatting, static analysis, and test runner.
- Add numbered, checksum-verified SQLite migrations.
- Implement stable IDs for programmes, questions, hypotheses, claims, sources, lineages, evidence, experiments, revisions, cycles, checkpoints, permissions, and evaluations.
- Implement append-only event streams with per-programme versions, causation/correlation IDs, payload schema versions, hashes, and idempotency keys.
- Implement transactional command handling and rebuildable read projections.
- Add foreign-key enforcement, bounded busy timeout, WAL compatibility decision, and supported backups.
- Add database integrity, event validation, projection rebuild/compare, and sanitized export commands.
- Store state only under the isolated `pgra` profile or an explicit test directory.

### Tests

- fresh install and every forward migration;
- invalid/mismatched migration checksum;
- constraints and cross-programme ownership;
- duplicate command retry and optimistic write conflict;
- crash injection at each transaction boundary;
- two-process access behavior;
- projection rebuild equivalence and deliberate drift detection;
- backup, restore, corrupt-artifact detection, and interrupted upgrade recovery;
- no read/write of the default Hermes profile.

### Exit gate

A synthetic programme created in one process is loaded and advanced in a second process with no conversation history; event and projection integrity checks pass.

## Phase 2 — Evidence integration and provenance

Connect bounded collection through interfaces, initially using deterministic fixtures and then verified Hermes tool adapters.

### Deliverables

- Source/snapshot capture with canonical URI, times, version/hash, access method, and limitations.
- Observation/interpretation separation and exact locators.
- Source-lineage graph with derivation types and unknown-lineage handling.
- Evidence stance, quality dimensions, verification state, and claim linkage.
- Deduplication that preserves distinct observations while grouping shared origins.
- Counterevidence search records, including attempted source classes and access gaps.
- Public-source and prompt-injection boundary.
- Adapters for available Hermes tools only after inspecting their actual contracts.

### Tests

- duplicate URL, canonicalization, changed snapshot, mirror, syndicated article, and common-origin cases;
- independent sources remain independent;
- counterevidence stays visible and cannot be silently filtered;
- blocked/rate-limited/login-gated sources become coverage gaps;
- remote instructions cannot alter policy or invoke unauthorized tools;
- citations resolve from claims to snapshots and lineage.

### Exit gate

A fixture-backed run produces an auditable claim/evidence graph in which URL count and independent lineage count differ correctly.

## Phase 3 — Hypotheses, belief revision, and experiments

Add explicit epistemic operations rather than free-form conclusions.

### Deliverables

- Competing hypotheses with scope, priors, alternatives, and falsifiers.
- Belief revisions requiring prior state, triggers, rationale, and unresolved objections.
- Domain-appropriate assessment representation, starting ordinally when numeric probabilities are not defensible.
- Experiment protocol, authorization, budget, expected result, attempts, artifacts, deviations, and cleanup.
- Failed/inconclusive experiment records.
- Synthesis with support, counterevidence, uncertainty, and change since checkpoint.

### Tests

- revisions cannot overwrite/orphan prior assessments or omit triggers;
- contradictory evidence is presented;
- experiments cannot execute before authorization and budget checks;
- failed attempts remain in history;
- report statements trace to evidence or are marked inference/unknown.

### Exit gate

A programme with competing hypotheses runs a safe synthetic experiment, records contradictory evidence, and produces an auditable belief revision.

## Phase 4 — Persistence and bounded cycles

Implement resumable execution and runtime controls.

### Deliverables

- Deterministic cycle state machine and leases.
- Objective, frozen policy, plan, checkpoint, terminal reason, and resume reference.
- Hard budgets for wall time, actions/tools, sources, artifacts/bytes, model usage/cost, experiments, and consecutive failures.
- Pause, resume, cancel, blocked, exhausted, failed, and completed paths.
- Idempotent outbox for reports/delivery.
- Operator commands for inspection and one-cycle execution.
- Cross-process recovery and stale-lease handling.
- Scheduler interface disabled and unconfigured by default.

### Tests

- every limit terminates a cycle;
- kill/restart at each transition resumes without duplicate side effects;
- duplicate wake-ups produce at most one logical cycle;
- approval waits do not consume uncontrolled budget;
- cancellation leaves a valid checkpoint;
- installation and ordinary runs create no scheduled task;
- default Hermes profile remains unchanged.

### Exit gate

A manual programme completes one cycle, the process terminates, and a clean new session resumes from the committed checkpoint. No schedule exists.

## Phase 5 — Meta-controller

Use accumulated data to improve research under separate governance.

### Deliverables

- Metrics for independent evidence quality per cost, uncertainty reduction, failures, calibration, and stop behavior.
- Meta-research records linked to input runs.
- Versioned strategy proposals with predicted benefit and evaluation plan.
- Human approval workflow for adoption.
- Guardrails preventing policy, permission, schedule, or budget escalation.

### Tests

- meta-analysis cannot mutate primary evidence;
- recommendations identify inputs and limitations;
- adoption requires explicit approval and an event;
- proposed strategies are evaluated on held-out/subsequent cases;
- metrics cannot be gamed by source duplication or hidden failures.

### Exit gate

The controller produces a reviewable recommendation from multiple runs but cannot activate it or expand authority autonomously.

## Phase 6 — Evaluations and release hardening

Evaluate PGRA against a one-shot baseline and harden integration.

### Deliverables

- Benchmarks spanning factual synthesis, evolving topics, conflicting sources, repo/tool research, and experiment-driven questions.
- Paired one-shot/persistent protocols with comparable models, tools, evidence policy, and total budgets.
- Rubric for correctness, citation entailment, provenance, lineage, counterevidence, calibration, continuity, reproducibility, safety, usefulness, latency, and cost.
- Cross-session test using a new process/session without chat context.
- Hermes adapter compatibility tests against the recorded version.
- Threat model, secret scan, dependency review, failure/backup/restore runbooks, and uninstall/isolation verification.
- Optional scheduler proof only after explicit opt-in; otherwise test the disabled adapter.
- Release notes separating verified behavior, mocks, limitations, and future work.

### Tests and review

- blind or independent review of a representative sample;
- adversarial prompt-injection and permission tests;
- degraded-source and network-failure tests;
- long-run budget/circuit-breaker tests;
- staged-file and history secret scan;
- install, upgrade, recovery, export, and uninstall scenarios;
- human review of migrations, permissions, evaluation fairness, and public claims.

### Exit gate

Publish paired evaluation artifacts and limitations. Pass all acceptance tests. Do not claim superiority where results are inconclusive.

## Optional post-MVP — opt-in scheduling

Only after Phases 1–6 and explicit user approval:

1. inspect the installed Hermes scheduling interface;
2. show cadence, timezone, next run, programme, budget, tools, delivery target, stop date;
3. require explicit confirmation;
4. create one idempotent wake-up path that executes at most one bounded cycle;
5. expose status and immediate disable controls;
6. trip a circuit breaker on repeated failure;
7. verify removal leaves programme state intact.

## Pull-request checklist

- [ ] Scope maps to a planned phase and preserves invariants.
- [ ] Actual Hermes version/interfaces were inspected when integration changed.
- [ ] Default profile is untouched; tests use `pgra` or disposable profiles.
- [ ] No cron/schedule is created by default.
- [ ] No secrets, sessions, private state, or real private source content is present.
- [ ] Migrations and recovery paths are tested.
- [ ] New behavior has tests and failure-path coverage.
- [ ] Event/projection and provenance invariants hold.
- [ ] Full tests, static checks, secret scan, and human diff review pass.
- [ ] Documentation distinguishes implementation, verification, mocks, and future work.
