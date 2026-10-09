CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE programmes (
    programme_id TEXT PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    objective TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft','active','paused','blocked','completed','cancelled','archived')),
    policy_json TEXT NOT NULL CHECK (json_valid(policy_json)),
    budget_json TEXT NOT NULL CHECK (json_valid(budget_json)),
    version INTEGER NOT NULL DEFAULT 0 CHECK (version >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    programme_id TEXT NOT NULL REFERENCES programmes(programme_id) ON DELETE RESTRICT,
    stream_version INTEGER NOT NULL CHECK (stream_version > 0),
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL,
    causation_id TEXT,
    correlation_id TEXT,
    idempotency_key TEXT,
    schema_version INTEGER NOT NULL DEFAULT 1,
    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
    payload_hash TEXT NOT NULL,
    UNIQUE (programme_id, stream_version),
    UNIQUE (programme_id, idempotency_key)
);

CREATE TRIGGER events_are_append_only_update
BEFORE UPDATE ON events BEGIN
    SELECT RAISE(ABORT, 'events are append-only');
END;

CREATE TRIGGER events_are_append_only_delete
BEFORE DELETE ON events BEGIN
    SELECT RAISE(ABORT, 'events are append-only');
END;

CREATE TABLE hypotheses (
    hypothesis_id TEXT PRIMARY KEY,
    programme_id TEXT NOT NULL REFERENCES programmes(programme_id) ON DELETE RESTRICT,
    statement TEXT NOT NULL,
    falsifier TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('proposed','active','supported','weakened','rejected','superseded','unresolved')),
    current_assessment TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY,
    programme_id TEXT NOT NULL REFERENCES programmes(programme_id) ON DELETE RESTRICT,
    statement TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE sources (
    source_id TEXT PRIMARY KEY,
    programme_id TEXT NOT NULL REFERENCES programmes(programme_id) ON DELETE RESTRICT,
    canonical_uri TEXT NOT NULL,
    title TEXT NOT NULL,
    source_type TEXT NOT NULL,
    publisher TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (programme_id, canonical_uri)
);

CREATE TABLE source_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE RESTRICT,
    observed_uri TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    published_at TEXT,
    content_hash TEXT,
    locator TEXT,
    access_status TEXT NOT NULL,
    metadata_json TEXT NOT NULL CHECK (json_valid(metadata_json))
);

CREATE TABLE source_lineage (
    lineage_id TEXT PRIMARY KEY,
    programme_id TEXT NOT NULL REFERENCES programmes(programme_id) ON DELETE RESTRICT,
    parent_source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE RESTRICT,
    child_source_id TEXT NOT NULL REFERENCES sources(source_id) ON DELETE RESTRICT,
    relation_type TEXT NOT NULL,
    rationale TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK (parent_source_id <> child_source_id),
    UNIQUE (parent_source_id, child_source_id, relation_type)
);

CREATE TABLE evidence_items (
    evidence_id TEXT PRIMARY KEY,
    programme_id TEXT NOT NULL REFERENCES programmes(programme_id) ON DELETE RESTRICT,
    claim_id TEXT REFERENCES claims(claim_id) ON DELETE RESTRICT,
    hypothesis_id TEXT REFERENCES hypotheses(hypothesis_id) ON DELETE RESTRICT,
    snapshot_id TEXT NOT NULL REFERENCES source_snapshots(snapshot_id) ON DELETE RESTRICT,
    stance TEXT NOT NULL CHECK (stance IN ('supports','contradicts','contextualizes','inconclusive')),
    observation TEXT NOT NULL,
    interpretation TEXT NOT NULL,
    quality_json TEXT NOT NULL CHECK (json_valid(quality_json)),
    lineage_group TEXT NOT NULL,
    verified INTEGER NOT NULL DEFAULT 0 CHECK (verified IN (0,1)),
    limitations TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK (claim_id IS NOT NULL OR hypothesis_id IS NOT NULL)
);

CREATE TABLE belief_revisions (
    revision_id TEXT PRIMARY KEY,
    programme_id TEXT NOT NULL REFERENCES programmes(programme_id) ON DELETE RESTRICT,
    hypothesis_id TEXT NOT NULL REFERENCES hypotheses(hypothesis_id) ON DELETE RESTRICT,
    prior_assessment TEXT NOT NULL,
    new_assessment TEXT NOT NULL,
    reasoning TEXT NOT NULL,
    trigger_evidence_json TEXT NOT NULL CHECK (json_valid(trigger_evidence_json)),
    parent_revision_id TEXT REFERENCES belief_revisions(revision_id) ON DELETE RESTRICT,
    created_at TEXT NOT NULL
);

CREATE TABLE experiments (
    experiment_id TEXT PRIMARY KEY,
    programme_id TEXT NOT NULL REFERENCES programmes(programme_id) ON DELETE RESTRICT,
    hypothesis_id TEXT NOT NULL REFERENCES hypotheses(hypothesis_id) ON DELETE RESTRICT,
    protocol TEXT NOT NULL,
    expected_observation TEXT NOT NULL,
    permission_status TEXT NOT NULL CHECK (permission_status IN ('pending','approved','denied')),
    budget_json TEXT NOT NULL CHECK (json_valid(budget_json)),
    stop_conditions TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('proposed','authorized','running','completed','failed','inconclusive','cancelled')),
    result_json TEXT CHECK (result_json IS NULL OR json_valid(result_json)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE research_cycles (
    cycle_id TEXT PRIMARY KEY,
    programme_id TEXT NOT NULL REFERENCES programmes(programme_id) ON DELETE RESTRICT,
    objective TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running','completed','paused','blocked','exhausted','failed','cancelled')),
    policy_json TEXT NOT NULL CHECK (json_valid(policy_json)),
    budget_json TEXT NOT NULL CHECK (json_valid(budget_json)),
    started_at TEXT NOT NULL,
    ended_at TEXT,
    terminal_reason TEXT
);

CREATE UNIQUE INDEX one_running_cycle_per_programme
ON research_cycles(programme_id) WHERE status = 'running';

CREATE TABLE checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    programme_id TEXT NOT NULL REFERENCES programmes(programme_id) ON DELETE RESTRICT,
    cycle_id TEXT REFERENCES research_cycles(cycle_id) ON DELETE RESTRICT,
    summary_json TEXT NOT NULL CHECK (json_valid(summary_json)),
    event_version INTEGER NOT NULL CHECK (event_version >= 0),
    created_at TEXT NOT NULL
);

CREATE TABLE evaluation_runs (
    evaluation_id TEXT PRIMARY KEY,
    programme_id TEXT REFERENCES programmes(programme_id) ON DELETE RESTRICT,
    benchmark_name TEXT NOT NULL,
    baseline_json TEXT NOT NULL CHECK (json_valid(baseline_json)),
    pgra_json TEXT NOT NULL CHECK (json_valid(pgra_json)),
    result_json TEXT NOT NULL CHECK (json_valid(result_json)),
    created_at TEXT NOT NULL
);

CREATE INDEX events_programme_idx ON events(programme_id, stream_version);
CREATE INDEX hypotheses_programme_idx ON hypotheses(programme_id);
CREATE INDEX claims_programme_idx ON claims(programme_id);
CREATE INDEX sources_programme_idx ON sources(programme_id);
CREATE INDEX evidence_programme_idx ON evidence_items(programme_id, stance);
CREATE INDEX revisions_hypothesis_idx ON belief_revisions(hypothesis_id, created_at);
CREATE INDEX checkpoints_programme_idx ON checkpoints(programme_id, created_at);
