ALTER TABLE source_snapshots ADD COLUMN excerpt TEXT;
ALTER TABLE source_snapshots ADD COLUMN artifact_path TEXT;
ALTER TABLE source_snapshots ADD COLUMN access_method TEXT NOT NULL DEFAULT 'manual';
ALTER TABLE source_snapshots ADD COLUMN transformations_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(transformations_json));

ALTER TABLE research_cycles ADD COLUMN stop_conditions TEXT NOT NULL DEFAULT 'Manual checkpoint required';

CREATE INDEX evidence_lineage_group_idx
ON evidence_items(programme_id, lineage_group);
