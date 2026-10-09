# Persistent General Research Agent (PGRA): complete design

## 1. Executive definition

PGRA is a persistent general research agent built as an isolated capability on top of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent). It borrows useful public-research patterns from [AlekseiUL/hermes-researcher-agent](https://github.com/AlekseiUL/hermes-researcher-agent), especially evidence gates, public-source boundaries, source-lineage awareness, counterexample search, degraded-access reporting, and reproducible artifacts.

PGRA extends those ideas from a strong research *run* into a durable research *programme*. The system can return to a question over multiple bounded cycles, retain structured state across sessions, run experiments, find evidence and counterevidence, revise beliefs transparently, and study its own research process. It must remain inspectable, permission-aware, budgeted, pausable, and safe by default.

The unit of continuity is not a conversation. It is a `ResearchProgramme` stored in a local SQLite database with an append-only event log. A chat, CLI invocation, or scheduled wake-up is merely one interface that may advance the programme.

## 2. Problem statement

One-shot research agents often produce useful briefs, but they have structural limits:

- they reconstruct context from prompts or chat transcripts;
- they conflate collected pages with independent evidence;
- they rarely preserve explicit hypotheses and rejected alternatives;
- they overwrite conclusions instead of recording belief change;
- they do not reliably resume after a process or conversation ends;
- they optimize for a polished answer rather than cumulative learning;
- they lack durable budgets, stop conditions, and audit trails;
- their claims of improvement are seldom compared with an equivalent one-shot baseline.

PGRA addresses these limitations with durable domain state, provenance-aware evidence, explicit epistemic operations, bounded execution, and evaluation.

## 3. Goals

1. Maintain many long-lived research programmes without depending on chat history.
2. Represent questions, hypotheses, claims, evidence, counterevidence, experiments, uncertainty, and belief revision explicitly.
3. Preserve source provenance and lineage from discovery through final synthesis.
4. Resume deterministically across processes and sessions.
5. Support manual cycles first and opt-in scheduled cycles later.
6. Enforce permissions, budgets, and stop conditions at runtime.
7. Make every material conclusion auditable back to sources and events.
8. Improve research strategy through bounded meta-research.
9. Compare persistent work with a one-shot baseline using repeatable evaluations.
10. Integrate with Hermes without changing the default profile.

## 4. Non-goals

- General autonomous computer control without a research objective.
- Unbounded self-prompting or indefinite background operation.
- Silent collection from private, paid, login-gated, or personally sensitive sources.
- Treating generated text, summaries, confidence scores, or popularity metrics as ground truth.
- Replacing domain experts or making high-stakes decisions without review.
- Mirroring all Hermes memories or conversations into the research database.
- Shipping credentials, private datasets, local state, or owner-specific configuration.
- Guaranteeing a specific Hermes command or plugin API before inspecting the installed version.

## 5. Product principles

### 5.1 Programme over conversation

A research programme is an addressable object with a stable ID, charter, scope, policy, status, budget, and history. Multiple conversations can operate on it. One conversation can inspect several programmes. Ending or resetting a chat does not end or erase a programme.

### 5.2 Events over silent mutation

Material state changes append immutable events. Current tables are projections for convenient reads. Historical assessments are superseded, not rewritten. A reviewer can answer: what changed, when, why, by which actor, using which evidence and policy?

### 5.3 Evidence over fluency

Claims must be linked to evidence records. Evidence records must be linked to captured sources and their lineage. A synthesis with smooth prose but missing lineage is incomplete.

### 5.4 Falsification over confirmation

For every decision-relevant hypothesis, the system records what would weaken or falsify it, searches for counterevidence, and reports coverage gaps when that search cannot be completed.

### 5.5 Bounded persistence over endless autonomy

Persistence means the ability to resume and accumulate structured knowledge. It does not mean continuous execution. Every cycle has limits and finishes in a terminal state such as completed, paused, blocked, failed, or exhausted.

### 5.6 Explicit authority over ambient capability

Having a browser, terminal, scheduler, or credential available does not imply permission to use it. Permissions are programme-scoped, action-specific, and deny by default.

## 6. Relationship to the reference projects

### NousResearch/hermes-agent

Hermes Agent is the host runtime and user interface. Current upstream documentation describes CLI and messaging interfaces, tools, skills, memory, sessions, profiles, subagents, and scheduled automations. PGRA should use verified extension points from the installed version for:

- a dedicated `pgra` profile;
- invoking PGRA commands or tools;
- tool permission mediation;
- manual and, only after opt-in, scheduled execution;
- presenting reports and approval requests.

These are integration intentions, not frozen API claims. The implementation must capture the tested Hermes version/commit and inspect `hermes --help`, profile commands, configuration, and source before deciding exact adapters.

### AlekseiUL/hermes-researcher-agent

The researcher profile is a methodological reference rather than a dependency that should be copied wholesale. PGRA should reuse or adapt, subject to license and version review:

- public-source safety boundaries;
- evidence quality and freshness gates;
- source-lineage grouping;
- counterexample search;
- reproducible research-run artifacts;
- degraded access reporting;
- separation of fact, interpretation, caveat, and recommended next move.

PGRA adds durable programmes, an event-sourced SQLite state engine, hypotheses, experiments, belief revision, bounded multi-cycle persistence, meta-research, and baseline evaluation.

## 7. Domain model

### 7.1 ResearchProgramme

The durable aggregate root.

Required fields:

- `programme_id`: stable UUID or sortable unique identifier;
- `slug`, `title`, and human-readable objective;
- `charter`: scope, exclusions, intended decision, audience, and success criteria;
- `status`: draft, active, paused, blocked, completed, cancelled, or archived;
- `policy_id` and immutable policy snapshot/hash for each cycle;
- cumulative and per-cycle budgets;
- created/updated timestamps and actor identifiers;
- active checkpoint and last terminal cycle;
- optional review date, never an implicit schedule.

Invariants:

- one programme owns its hypotheses, evidence, experiments, and revisions;
- activation requires a charter, permissions, budget, and stop conditions;
- completed/cancelled programmes cannot run until explicitly reopened;
- deletion is an explicit administrative event; ordinary workflows archive.

### 7.2 ResearchQuestion

A programme may contain a primary question and decomposed subquestions. Each question records priority, status, dependencies, answerability, and the decision it informs. Questions are versioned because scope changes can invalidate comparisons.

### 7.3 Hypothesis

A falsifiable candidate answer or explanatory model. It records its statement, scope, prior assessment and rationale, current projected assessment, alternatives, dependencies, falsifiers or expected observations, status, creator, and timestamps. Hypotheses do not store a single mutable confidence as history. Changes are represented by `BeliefRevision` events.

### 7.4 Claim

An atomic proposition suitable for support or challenge. Reports cite claims rather than attaching a pile of sources to a paragraph. A claim can support or oppose one or more hypotheses.

### 7.5 Source and SourceSnapshot

`Source` identifies the conceptual source: publication, repository, dataset, interview, page, or document. `SourceSnapshot` represents what was actually observed at a particular time.

Capture where policy and law permit:

- canonical and observed URI;
- source type, publisher/author, published and retrieved times;
- title, version, commit, release, or content hash;
- access method and tool version;
- excerpt or normalized artifact location;
- freshness and primary/secondary classification;
- access limitations, robots/login/rate-limit status, and transformation history.

Raw copyrighted content should not be copied unnecessarily. Prefer hashes, metadata, short excerpts, and references, with local private artifacts governed separately.

### 7.6 SourceLineage

Lineage prevents false corroboration. It models derivation relationships such as a mirror, an article reporting a vendor announcement, a transformed dataset, generated documentation, or multiple posts repeating one press release. Evidence aggregation counts independent lineages, not URLs. Unknown lineage remains unknown rather than being assumed independent.

### 7.7 EvidenceItem

An evidence item links a claim to a source snapshot with:

- stance: supports, contradicts, contextualizes, or inconclusive;
- exact locator or extraction reference;
- observation separated from interpretation;
- quality dimensions such as directness, source authority, methodology, freshness, and independence;
- lineage group;
- collection actor/tool and verification status;
- limitations and challenge notes.

`CounterEvidence` is not a different storage species; it is evidence whose stance challenges a claim or hypothesis, with explicit search coverage. This keeps the model symmetric while allowing the UI to foreground contradiction.

### 7.8 Experiment

An experiment is a bounded action designed to discriminate between hypotheses or reduce uncertainty. Examples include reproducing a benchmark, running a controlled query, checking a software behavior, or comparing prediction with a later observation.

Each experiment requires question/hypothesis linkage, protocol, expected discriminating result, permissions, risk class, budgets, environment, stop conditions, cleanup plan, status, attempt history, observations, artifacts, failures, and interpretation. An external side effect, paid operation, credential use, destructive action, or high-risk code execution requires explicit approval under policy.

### 7.9 BeliefRevision

A belief revision records the hypothesis, prior assessment, new assessment, calibration representation, triggering evidence/counterevidence/experiment, reasoning, unresolved objections, actor/model/tool versions, time, and parent revision. It cannot delete the prior state. Reports can reconstruct the belief trajectory and identify reversals unsupported by new evidence.

### 7.10 ResearchCycle

A bounded attempt to advance a programme. It has an objective, input checkpoint, frozen policy snapshot, budgets, plan, executed actions, output checkpoint, and terminal reason.

Allowed terminal states are `completed`, `paused`, `blocked`, `exhausted`, `failed`, and `cancelled`. There is no implicit self-enqueue at the end of a cycle.

### 7.11 MetaResearchRecord

Meta-research examines the process: source strategies, hypotheses that consumed budget without reducing uncertainty, extraction/summarization error, calibration, and stop-rule behavior. It can recommend changes but cannot silently loosen permissions, increase budgets, enable scheduling, or rewrite evidence.

## 8. SQLite Research State Engine

SQLite is the initial authoritative store because it is portable, transactional, inspectable, easy to back up, and sufficient for a single-node/local-first profile. It is not chosen as a universal scaling claim.

### 8.1 Storage layout

```text
<profile-state>/pgra/
  pgra.sqlite3
  artifacts/
    <programme-id>/...
  backups/
  exports/
```

This location must be outside the public repository or under an ignored path. The adapter resolves it from the isolated `pgra` profile rather than the default profile.

### 8.2 Core tables

The exact migration syntax may evolve, but the initial schema should include:

```sql
CREATE TABLE schema_migrations (
  version INTEGER PRIMARY KEY,
  applied_at TEXT NOT NULL,
  checksum TEXT NOT NULL
);

CREATE TABLE programmes (
  programme_id TEXT PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  objective TEXT NOT NULL,
  charter_json TEXT NOT NULL,
  status TEXT NOT NULL,
  policy_json TEXT NOT NULL,
  policy_hash TEXT NOT NULL,
  budget_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  version INTEGER NOT NULL
);

CREATE TABLE events (
  event_id TEXT PRIMARY KEY,
  programme_id TEXT NOT NULL,
  stream_version INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  occurred_at TEXT NOT NULL,
  actor_json TEXT NOT NULL,
  causation_id TEXT,
  correlation_id TEXT,
  idempotency_key TEXT,
  payload_json TEXT NOT NULL,
  payload_hash TEXT NOT NULL,
  FOREIGN KEY (programme_id) REFERENCES programmes(programme_id),
  UNIQUE (programme_id, stream_version),
  UNIQUE (programme_id, idempotency_key)
);

CREATE TABLE questions (...);
CREATE TABLE hypotheses (...);
CREATE TABLE claims (...);
CREATE TABLE sources (...);
CREATE TABLE source_snapshots (...);
CREATE TABLE source_lineage (...);
CREATE TABLE evidence_items (...);
CREATE TABLE experiments (...);
CREATE TABLE experiment_attempts (...);
CREATE TABLE belief_revisions (...);
CREATE TABLE research_cycles (...);
CREATE TABLE checkpoints (...);
CREATE TABLE permission_decisions (...);
CREATE TABLE meta_research_records (...);
CREATE TABLE evaluation_runs (...);
```

Ellipses are deliberately not implementation-ready SQL. Phase 1 must turn this conceptual schema into migrations with explicit columns, foreign keys, indexes, `CHECK` constraints, and JSON validation appropriate to the selected SQLite binding.

### 8.3 Transaction rule

An authoritative command executes as one transaction:

1. load stream/projection version;
2. validate command and policy;
3. append one or more events using optimistic version control;
4. update projections;
5. write an outbox item if an external notification is required;
6. commit;
7. perform external delivery from the outbox, idempotently.

No report, notification, or scheduler acknowledgment should claim success before the commit.

### 8.4 Event envelope

Every event includes stable identity, aggregate/stream version, UTC time, actor, causation/correlation IDs, schema version, payload hash, and typed payload. Event types should be past-tense facts, for example `ProgrammeCreated`, `ProgrammeActivated`, `HypothesisProposed`, `SourceObserved`, `LineageLinked`, `EvidenceRecorded`, `ExperimentAuthorized`, `ExperimentCompleted`, `BeliefRevised`, `BudgetExhausted`, `PermissionDenied`, and `CheckpointCreated`.

### 8.5 Projection rebuild and integrity

The implementation must rebuild projections into temporary tables from events, compare them with live projections, and atomically replace or report drift. Integrity commands run `PRAGMA integrity_check`, verify migration checksums, validate event payload schemas, detect broken artifact hashes, and identify orphaned relationships.

### 8.6 Concurrency and recovery

- Enable foreign keys on every connection.
- Use WAL when compatible with the deployment filesystem.
- Configure a bounded busy timeout.
- Serialize writes or use optimistic stream versions.
- Make command retries idempotent.
- Crash tests cover failure before append, between append/projection, and after commit before delivery.
- Backups use SQLite's supported backup mechanism, not unsafe copying of an active database.
- A checkpoint records logical progress; it is not a substitute for database backup.

## 9. Research lifecycle

### 9.1 Create and frame

The user defines the question, decision context, scope, exclusions, desired evidence standard, time horizon, budgets, permissions, and success/stop criteria. The system creates a draft programme, decomposes the question, proposes competing hypotheses, records provisional priors, defines falsifiers, and identifies likely source classes.

### 9.2 Plan a bounded cycle

Choose one objective based on expected information value. Freeze policy and allocate limits: wall time, model/tool calls, sources, bytes/artifacts, experiments, monetary cost, and maximum consecutive failures. Produce a plan that terminates cleanly.

### 9.3 Collect, normalize, and challenge

Collect within permission boundaries. Capture source identity, snapshot metadata, lineage hints, exact locators, transformations, and access gaps. Separate raw observation from interpretation. For material claims, search for alternatives, negative results, contradictory measurements, and methodological criticisms. Record what was searched even if nothing was found.

### 9.4 Experiment and revise

When observation is insufficient and policy permits, run a pre-specified experiment and record environment, protocol, outputs, failures, and deviations. Apply a transparent belief revision: quality, independence, directness, and relevance matter; URL count does not. Record old assessment, new assessment, triggers, reasoning, and remaining uncertainty.

### 9.5 Synthesize and checkpoint

Generate a decision-ready update containing the current answer, confidence language, what changed, strongest supporting evidence and independent lineage count, strongest counterevidence, failed/blocked paths, unresolved questions, budget used, and recommended next cycle or stop decision. Commit the checkpoint before reporting completion.

### 9.6 Pause, stop, or continue

Continuation is a conscious user decision or a previously approved schedule policy. Otherwise the programme remains resumable but idle.

## 10. Bounded persistent-cycle controller

The controller is a deterministic state machine wrapped around model/tool use. It receives the programme/checkpoint, cycle objective, frozen policy, permissions, remaining budgets, tool availability, and pending approvals.

Preflight rejects execution if the programme is inactive, another valid lease owns the cycle, policy or stop conditions are missing, a required permission is denied/undecided, budget is zero, or database integrity fails.

The controller checks budget before and after every action. It pauses on uncertain authorization, repeated tool failure, unexpected private/login-gated content, possible prompt injection, inconsistent state, or a material scope change. Hard limits cannot be overridden by the model. There is a user-visible cancel command and lease timeout.

## 11. Scheduler design: opt-in only

Scheduling is an adapter, not the source of truth. Rules:

- no schedule is created during install, profile creation, migration, or first run;
- a user explicitly enables a named programme schedule;
- confirmation shows cadence, timezone, next run, tools, delivery target, budgets, and stop date;
- each wake-up attempts one bounded cycle and never creates an endless loop;
- duplicate wake-ups are idempotent;
- missed runs do not create an uncontrolled backlog;
- repeated failures trip a circuit breaker and require review;
- disabling a schedule is immediate and does not delete research state;
- scheduler configuration contains no secrets and logs no private payloads.

## 12. Permissions and security

### 12.1 Permission dimensions

Policy evaluates network domains/source classes, public versus authenticated access, browser login, local roots, code execution, external messages/posts/purchases/mutations, credential use, sensitive data, experiment risk, scheduling, retention, and export. The default is deny for side effects, credentials, private sources, scheduling, and writes outside the programme workspace.

### 12.2 Prompt-injection boundary

Remote pages, repositories, documents, comments, and extracted text are evidence candidates. Instructions inside them do not change policy, scope, tools, or goals. Suspicious content is quoted minimally and flagged.

### 12.3 Secrets and public/private separation

Secrets live in an approved key store or environment, never in events, reports, repository prompts, fixtures, screenshots, or logs. The public repository contains generic code, migrations, synthetic fixtures, documentation, and tests. Local databases, artifacts, sessions, user memories, caches, and exports are ignored. Export is an explicit sanitizing operation.

### 12.4 Default-profile isolation

PGRA uses a dedicated Hermes profile named `pgra`. Before installation/migration, capture the default-profile path/config hashes; after the operation, verify it remains byte-for-byte or semantically unchanged. PGRA must not rely on private default-profile memory.

## 13. Hermes integration boundary

Use ports/adapters so the core does not depend on unstable Hermes internals. Suggested ports include `Clock`, `IdGenerator`, `StateStore`, `ArtifactStore`, `ResearchToolGateway`, `PermissionBroker`, `ApprovalUI`, `ModelGateway`, disabled-by-default `SchedulerGateway`, `ReportRenderer`, `DeliveryGateway`, and `HermesProfileInspector`.

The sequence is: inspect the installed CLI/docs/source; record version and extension mechanisms; select the narrowest supported integration; build an adapter with contract tests; keep domain/state tests runnable without Hermes; document compatibility and failure behavior. User operation names such as create, inspect, run-one-cycle, pause, resume, export, integrity-check, evaluate, schedule-enable, and schedule-disable are illustrative until verified.

## 14. Meta-research controller

Meta-research runs only after enough primary-cycle data exists and within its own budget. It may compare source strategies by useful independent evidence per cost, identify lineage/extraction failures, measure calibration, and propose question/stop-rule/experiment changes.

It may not mark its own recommendation accepted, change permission policy, enable schedules, erase failed runs, optimize only for volume/confidence/agreement, or export private programme data without approval. Recommendations are versioned proposals reviewed by a human or separate governed process.

## 15. Reporting and observability

Every cycle report includes programme/cycle IDs, checkpoint, tested runtime version, objective, status, sources and independent lineages, evidence/counterevidence, belief changes, experiments, limits, access gaps, costs, and next action.

Telemetry is privacy-minimized: durations, counts, statuses, budgets, retries, error classes, actor/model/tool/version, and correlation IDs. It excludes credentials and unnecessary source bodies.

## 16. Evaluation against a one-shot baseline

Each benchmark runs in two conditions:

- **One-shot baseline:** same question, evidence policy, source/tool access, model family, and comparable total budget, without prior programme state.
- **PGRA condition:** one or more cycles resumed across a fresh process/session from SQLite.

Where exact equality is unavailable, record the difference and avoid causal overclaiming.

Evaluate factual correctness, citation entailment, provenance/lineage, counterevidence, calibration, hypothesis discrimination, belief revision, cross-session continuity, reproducibility, policy compliance, isolation, latency, tool/model usage, cost, and decision usefulness. Use paired tasks, predefined rubrics, blind review where practical, and saved artifacts. Report regressions and null results.

## 17. Acceptance criteria

### State engine

- A programme created in process A is resumed in process B without chat history.
- Events are append-only, ordered per programme, and idempotent under retry.
- Projections rebuild equivalently and drift is detectable.
- Crash-injection never produces a half-committed authoritative update.
- Backup/restore and migration recovery are tested.

### Evidence and epistemics

- Every report claim traces to evidence or is labeled inference/unknown.
- Derived sources share a lineage and do not inflate corroboration.
- Counterevidence search coverage is recorded for material hypotheses.
- Belief revisions retain prior state and cite triggers.
- Failed and inconclusive experiments remain visible.

### Control and safety

- Every cycle terminates under a tested limit.
- Scheduling is absent/disabled after install and profile creation.
- Enabling scheduling requires explicit opt-in and displays effective policy.
- Denied actions cannot be executed by model instruction or remote content.
- The default Hermes profile is unchanged after install, run, upgrade, and uninstall tests.
- Secret scanning and repository inspection find no private runtime state.

### Evaluation

- At least one suite executes both PGRA and one-shot conditions.
- Results include raw artifacts, rubric, versions, budgets, and limitations.
- Cross-session persistence is demonstrated with separate processes.
- No improvement claim is published without paired evidence.

## 18. Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Confirmation bias compounds | competing hypotheses, counterevidence gate, lineage counts, belief audit |
| Stale evidence persists | timestamps, freshness policy, invalidation/recheck events |
| Duplication creates false confidence | lineage graph and independence-aware aggregation |
| Cost runaway | hard per-action/cycle/programme budgets and no implicit requeue |
| Scheduler surprises user | no cron by default, explicit confirmation, stop date, circuit breaker |
| Prompt injection changes behavior | untrusted-source boundary and external policy checks |
| SQLite corruption/concurrency | transactions, WAL where safe, backups, integrity checks, write control |
| Hermes changes | version inspection, adapter boundary, compatibility tests |
| Private state leaks | external state directory, ignore rules, secret scan, sanitized exports |
| Wrong meta metric | multi-dimensional evaluation and approval of strategy changes |

## 19. Open design decisions

Resolve after inspecting the target environment: implementation language/SQLite binding; exact Hermes packaging/invocation; JSON versus normalized projections; artifact encryption/retention; ordinal versus probabilistic assessments; multi-process writer strategy; evaluation datasets/adjudication; export format; and scheduler/delivery adapter if explicitly requested.

## 20. Definition of done

PGRA is not done when documents exist or a demo returns a report. It is done for an initial release when the isolated `pgra` profile can create and advance a programme; persist and rebuild auditable SQLite state; capture provenance, lineage, counterevidence, experiments, and revisions; stop under policy; resume in a new session; leave the default profile untouched; keep scheduling off unless opted in; pass security/recovery tests; and publish a paired evaluation against a one-shot baseline with limitations.
