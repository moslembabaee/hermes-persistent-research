# PGRA CLI reference

The runtime uses only the Python standard library. Run it from the installed profile root:

```bash
python pgra.py --help
```

State defaults to `$HERMES_HOME/pgra/pgra.sqlite3`. Override it with `PGRA_DB` or the global `--db PATH` option. Every command emits JSON; preserve returned IDs for later commands.

## Initialize and inspect

```bash
python pgra.py init
python pgra.py integrity
python pgra.py programme list
python pgra.py programme show <slug-or-programme-id>
```

`integrity` checks SQLite integrity, foreign keys, contiguous event streams, projection stream versions, event JSON, and event payload hashes.

## Programme lifecycle

```bash
python pgra.py programme create --slug <slug> --title <title> --objective <objective> \
  --policy-json '{}' --budget-json '{}'
python pgra.py programme pause <programme> --reason <reason>
python pgra.py programme resume <programme> --reason <reason>
python pgra.py programme complete <programme> --reason <reason>
python pgra.py programme cancel <programme> --reason <reason>
python pgra.py programme archive <programme> --reason <reason>
```

## Bounded cycles and checkpoints

```bash
python pgra.py cycle start <programme> --objective <objective> --budget-json '{}'
python pgra.py cycle checkpoint <programme> --cycle <cycle-id> \
  --summary-json '{"result":"...","open_questions":[]}' \
  --status completed --reason "bounded cycle finished"
```

Only one cycle may be running per programme. A paused/blocked/completed/cancelled/archived programme cannot start a cycle until explicitly returned to `active` where allowed.

## Hypotheses and claims

```bash
python pgra.py hypothesis add <programme> --statement <statement> \
  --assessment uncertain --falsifier <falsifier>
python pgra.py claim add <programme> --statement <atomic-claim>
```

## Sources, snapshots, and lineage

```bash
python pgra.py source add <programme> --uri <https-url> --title <title> --type primary
python pgra.py source snapshot <programme> <source-id> --observed-uri <https-url> \
  --locator <locator> --content-hash <sha256> --access-status available --metadata-json '{}'
python pgra.py lineage link <programme> <parent-source-id> <child-source-id> \
  --relation mirror --rationale "Republished from the parent"
```

## Evidence and belief revision

Evidence must reference a source snapshot and at least one claim or hypothesis.

```bash
python pgra.py evidence add <programme> --snapshot <snapshot-id> \
  --hypothesis <hypothesis-id> --claim <claim-id> --stance supports \
  --observation <observation> --interpretation <interpretation> \
  --lineage-group <lineage-id-or-group> --quality-json '{}' --verified

python pgra.py hypothesis revise <programme> <hypothesis-id> \
  --assessment likely --reasoning <reasoning> --evidence <evidence-id> [<evidence-id> ...]
```

A revision without evidence is rejected. Earlier assessments remain in `belief_revisions`.

## Experiments

```bash
python pgra.py experiment add <programme> <hypothesis-id> --protocol <protocol> \
  --expected-observation <observation> --budget-json '{}' --stop-conditions <conditions>
python pgra.py experiment authorize <programme> <experiment-id> --approve --reason <reason>
python pgra.py experiment finish <programme> <experiment-id> \
  --status completed --result-json '{}'
```

An experiment cannot be completed unless it was explicitly approved. The CLI records experiments; it does not execute external side effects.

## Paired evaluation

Prepare two JSON files with identical metric keys:

```json
{
  "metrics": {
    "factual_correctness": 0.8,
    "provenance_completeness": 0.7
  },
  "conditions": {"model": "same", "budget": 10},
  "cost": {"usd": 1.25, "seconds": 90}
}
```

Then compare and persist the result:

```bash
python pgra.py evaluation compare --programme <programme> --name <benchmark-name> \
  --baseline baseline.json --pgra pgra.json
```

The runner calculates per-metric deltas, mean delta, wins/ties/losses, cost metadata, and whether conditions match. It does not manufacture scores or claim causality.

## Cross-process persistence verification

```bash
python -m unittest tests.test_cross_session_cli -v
```

The test creates a programme and checkpoint through separate CLI processes, then opens a clean third process using only the SQLite path and stable programme slug.
