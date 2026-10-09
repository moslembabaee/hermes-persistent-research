# Backup and recovery

PGRA uses SQLite in WAL mode. Copying only the active `.sqlite3` file can omit committed data still represented by sidecar files, so use the CLI backup command.

## Create and verify a backup

```text
python pgra.py integrity
python pgra.py backup create .pgra/backups/pgra.sqlite3
```

The command uses SQLite's online backup API and runs `PRAGMA integrity_check` on the result before reporting success.

## Restore

Stop active PGRA writers, then run:

```text
python pgra.py backup restore .pgra/backups/pgra.sqlite3 --confirm-restore
python pgra.py integrity
```

The restore command validates the source backup and creates `<active-database>.before-restore` before replacement. Keep that safety copy until the restored programme has been inspected.

## Projection drift

Database integrity and projection integrity are separate checks:

```text
python pgra.py projection status
python pgra.py projection rebuild PROGRAMME
python pgra.py integrity
```

`projection rebuild` replaces only derived programme tables using the most recent complete projection captured in the append-only event stream. It does not delete or rewrite events.
