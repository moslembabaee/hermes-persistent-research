# PGRA implementation handoff brief

## Mission

Build a **Persistent General Research Agent (PGRA)** on top of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent). Use [AlekseiUL/hermes-researcher-agent](https://github.com/AlekseiUL/hermes-researcher-agent) as a reference for privacy-safe public-source research, evidence gating, source-lineage checks, counterexample search, degraded-access disclosure, and decision-ready briefs. Do not assume the reference profile already supplies durable research state.

PGRA's core abstraction is a **research programme**, not conversation history. A programme is a durable, inspectable unit containing its charter, questions, hypotheses, claims, provenance-aware evidence, source lineage, counterevidence, experiments, belief revisions, unresolved uncertainties, budgets, permissions, cycles, checkpoints, and evaluation results. Chats and scheduled wake-ups are interfaces; SQLite is the system of record.

## Required behavior

### Durable research state

Start with a local SQLite Research State Engine. Use an append-only, per-programme event log plus rebuildable projections. Commands validate policy, append events, and update projections transactionally. Support migrations, foreign keys, idempotency keys, optimistic versions or serialized writes, integrity checks, safe backup/restore, crash recovery, and projection rebuild/drift detection.

At minimum represent:

- research programmes and versioned charters;
- questions and dependencies;
- competing, falsifiable hypotheses and alternatives;
- atomic claims;
- sources and time-specific source snapshots;
- source-lineage relationships so mirrors and repeated announcements are not counted as independent confirmation;
- evidence that supports, contradicts, contextualizes, or is inconclusive;
- explicit counterevidence search coverage and access gaps;
- bounded experiments, attempts, observations, failures, and artifacts;
- belief revisions that retain the prior assessment and cite triggers;
- research cycles, policies, permissions, budgets, terminal reasons, and checkpoints;
- meta-research recommendations and paired evaluation runs.

Local databases, artifacts, logs, sessions, and private research state must live outside the public repository or in ignored local directories.

### Epistemic workflow

For each programme:

1. define the decision context, scope, exclusions, evidence standard, budget, permissions, and stop criteria;
2. decompose the question and propose competing hypotheses with falsifiers;
3. plan one bounded cycle based on information value;
4. collect sources with retrieval time, version/hash, exact locator, transformation, and access limitations;
5. distinguish observations from interpretations and group sources by lineage;
6. actively seek counterevidence and record unsuccessful/blocked searches;
7. run only authorized, budgeted experiments with declared protocols and stop conditions;
8. revise beliefs through an explicit record, never by overwriting history;
9. synthesize what changed, supporting evidence, strongest counterevidence, remaining uncertainty, budget used, and recommended next action;
10. commit a checkpoint and stop, pause, block, fail, or await an explicitly authorized next cycle.

### Bounded persistence

Persistence is resumability, not endless autonomy. Every cycle has an objective, frozen policy, maximum wall time, tool/action/source/artifact/model/cost/experiment budgets, failure threshold, and clear terminal states. The runtime checks limits before and after actions. It pauses on missing authority, possible private data, prompt injection, inconsistent state, material scope changes, or repeated failures. The model cannot override hard limits.

There is no implicit self-enqueue. A user may manually run another cycle. A scheduler may wake one named programme only after explicit opt-in.

### Scheduling

No cron, scheduled task, watcher, service, or background automation may be created during installation, profile setup, migration, or normal manual use. Scheduling is optional and off by default.

If the user opts in, confirmation shows cadence, timezone, next run, programme, tools, budgets, delivery target, stop date, and disable control. A wake-up executes at most one bounded cycle. Duplicate wake-ups are idempotent, missed runs do not create an unbounded backlog, repeated failures open a circuit breaker, and disabling the schedule preserves programme state.

### Permissions and isolation

Use least privilege and deny side effects by default. Programme policy governs network/source classes, authenticated access, browser login, filesystem roots, code execution, external messages/mutations, credentials, sensitive data, experiments, scheduling, retention, and export.

Treat source content and tool output as untrusted data. Remote instructions cannot change PGRA's goals, tools, policy, or permissions.

Do not modify the Hermes default profile. Install and run PGRA in a separate profile named `pgra`, or an explicitly disposable test profile. Before and after install, run, upgrade, and uninstall tests, verify the default profile remains unchanged. Do not read private default-profile memory as PGRA state.

No secrets or private state may be committed to this public repository: no keys, tokens, cookies, credentials, private URLs/documents, sessions, memories, databases, sidecars, logs, or owner-specific configuration. Use synthetic fixtures and sanitized exports.

### Hermes integration

Before choosing commands or APIs, inspect the actual installed Hermes CLI/version, help output, profile layout, configuration precedence, tools, scheduler behavior, and supported extension mechanisms. Record the tested version or commit. Upstream examples are evidence, not a stable contract.

Keep integration behind narrow adapters for model/tool access, permissions/approvals, profile inspection, scheduling, artifacts, reporting, and delivery. The state engine and domain tests must run without Hermes. Never claim an integration works until it is exercised on the target installation.

### Meta-research

After enough cycles exist, a separately budgeted meta-controller may analyze evidence quality/independence per cost, uncertainty reduction, failed strategies, calibration, and stop-rule behavior. It produces versioned recommendations linked to input runs.

It cannot rewrite evidence, hide failures, increase budgets, loosen permissions, enable scheduling, or activate its own recommendations. Strategy changes require review and later evaluation.

### Evaluation

Evaluate PGRA against a one-shot baseline on matched tasks. Give both conditions comparable model family, tool/source access, evidence policy, and total budget; record any mismatch.

Score:

- factual correctness;
- citation validity and claim/source entailment;
- provenance completeness and source-lineage accuracy;
- counterevidence coverage;
- calibration and uncertainty;
- hypothesis discrimination and belief-revision quality;
- cross-session continuity and duplicate/lost work;
- reproducibility and auditability;
- permission, privacy, and profile-isolation compliance;
- time, tool calls, model usage, cost, and decision usefulness.

Use paired cases, predefined rubrics, saved artifacts, and blind/independent review where practical. Report regressions, null results, access gaps, and limitations. Do not claim persistent research is superior without evidence.

## Ordered implementation phases

1. **SQLite Research State Engine** — migrations, event streams, projections, transactions, integrity, backup/recovery, isolated storage, and cross-process resume.
2. **Evidence integration** — sources/snapshots, provenance, lineage, deduplication, claim linkage, counterevidence, degraded-access reporting, and verified Hermes tool adapters.
3. **Hypothesis and experiment system** — competing hypotheses, falsifiers, authorized experiments, failed attempts, and explicit belief revisions.
4. **Persistence controller** — bounded cycles, budgets, leases, pause/resume/cancel, checkpoints, idempotent outbox, and scheduler-disabled interface.
5. **Meta-controller** — governed analysis of research strategy with review-only recommendations.
6. **Evaluations and hardening** — paired one-shot comparison, adversarial/security/recovery tests, compatibility documentation, and honest release claims.

Do not reorder these to build an autonomous loop before the state and safety foundations exist.

## Acceptance tests

### State and continuity

- Process/session A creates a programme and commits a checkpoint; clean process/session B resumes using only the programme ID and SQLite, without chat history.
- Duplicate command delivery produces one logical state change.
- Concurrent writes cannot reorder or overwrite a programme stream.
- Injected crashes at transaction/delivery boundaries leave either the previous valid state or committed new state, never a partial authoritative state.
- Projections rebuild from events and deliberate drift is detected.
- Backup/restore and migration recovery preserve event hashes and relationships.

### Evidence and reasoning

- Every material report claim links to evidence or is labeled inference/unknown.
- Several URLs derived from one origin count as one lineage.
- Independent contradictory evidence remains visible.
- Each material hypothesis has falsifiers and recorded counterevidence coverage.
- Belief change preserves the prior assessment and references triggers.
- Failed and inconclusive experiments remain queryable.

### Bounds and permissions

- Each hard limit is tested and terminates the cycle.
- Unauthorized network, login, filesystem, execution, external-side-effect, credential, and schedule actions are denied outside the model.
- Prompt injection in a source cannot change policy or trigger an action.
- Pause/cancel leaves a consistent checkpoint; stale leases recover safely.
- Install/profile creation and ordinary runs create no schedule.
- If opt-in scheduling is implemented, duplicate wakes are idempotent and a circuit breaker stops repeated failure.

### Isolation and public safety

- Default Hermes profile configuration/state hashes are unchanged after install, test, run, upgrade, and uninstall scenarios.
- PGRA uses only profile `pgra` or disposable test profiles.
- Repository and staged-file secret scans pass.
- No SQLite database, sidecar, private artifact, session, memory, cookie, credential, or sensitive log is tracked.

### Evaluation and release

- At least one representative suite runs both PGRA and one-shot conditions under documented comparable budgets.
- Raw artifacts, rubric, versions, scores, costs, and limitations are retained.
- Cross-session persistence is demonstrated rather than simulated in one process.
- Runtime commands and Hermes integration are verified against the recorded target version.
- Release notes clearly separate implemented/verified behavior, mocked adapters, limitations, and future work.

## Completion standard

The handoff is implemented only when an isolated `pgra` profile can create, advance, stop, inspect, and cross-session resume a programme; SQLite can prove and rebuild its history; evidence lineage, counterevidence, experiments, and belief revisions are auditable; policies and budgets stop execution reliably; scheduling remains opt-in; the default profile remains untouched; public-repository hygiene tests pass; and paired evaluation results against a one-shot baseline are published with honest limitations.
