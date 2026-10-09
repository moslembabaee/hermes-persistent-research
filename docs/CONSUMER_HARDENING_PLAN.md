# Consumer hardening plan

This plan turns the 0.2 technical MVP into a safer and clearer 0.3 consumer release without adding external memory systems or background services.

## Completed in 0.3.0

1. **Trustworthy state**
   - Add migration `002_consumer_hardening.sql` without changing migration 001.
   - Capture a complete projection after every authoritative event.
   - Upgrade older streams with a one-time projection baseline.
   - Detect projection drift and rebuild a programme from the latest event snapshot.
   - Verify local artifact hashes during integrity checks.

2. **Domain guardrails**
   - Validate required text, controlled vocabularies, SHA-256 hashes, and normalized evaluation scores.
   - Enforce programme and cycle count budgets.
   - Reject invalid programme and experiment state transitions.
   - Reject belief revisions triggered by evidence attached to another hypothesis.

3. **Evidence durability**
   - Store access method, transformations, a permitted excerpt, and an optional local artifact reference.
   - Require locator and content hash for available or partially available snapshots.
   - Keep artifact paths out of sanitized public exports.

4. **Consumer operations**
   - Add `doctor`, summary/list commands, Markdown report, sanitized JSON export, projection status/rebuild, and evaluation templates.
   - Add SQLite-safe online backup and confirmed restore with a safety copy.
   - Provide cross-platform one-line examples and an explicit first-run path.

5. **Public release hygiene**
   - Document Python and Hermes requirements, verified versus absent behavior, backup/recovery, and known limitations.
   - Add changelog, license, CI workflow, and release metadata.

## Deliberately deferred

These items would add architectural complexity and are not required for the local-first consumer release:

- Hindsight, Obsidian, PostgreSQL, or vector storage;
- automatic Hermes tool hooks;
- command receipt/idempotency infrastructure;
- live token, cost, wall-time, and tool-call metering;
- a meta-controller;
- scheduling of any kind.

Deferred items remain clearly labeled and are not implied by the package description.
