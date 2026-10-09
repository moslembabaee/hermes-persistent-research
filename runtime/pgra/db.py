from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Iterator


class MigrationError(RuntimeError):
    pass


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    @property
    def migration_dir(self) -> Path:
        return Path(__file__).with_name("migrations")

    @contextlib.contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    def migrate(self) -> None:
        migrations = sorted(self.migration_dir.glob("[0-9][0-9][0-9]_*.sql"))
        if not migrations:
            raise MigrationError("No migrations found")
        with self.session() as connection:
            existing = {}
            table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
            ).fetchone()
            if table:
                existing = {
                    row["version"]: row["checksum"]
                    for row in connection.execute("SELECT version, checksum FROM schema_migrations")
                }
            for migration in migrations:
                version = int(migration.name.split("_", 1)[0])
                body = migration.read_text(encoding="utf-8")
                checksum = hashlib.sha256(body.encode("utf-8")).hexdigest()
                if version in existing:
                    if existing[version] != checksum:
                        raise MigrationError(f"Migration checksum mismatch: {migration.name}")
                    continue
                escaped_name = migration.name.replace("'", "''")
                script = (
                    "BEGIN IMMEDIATE;\n"
                    + body
                    + "\nINSERT INTO schema_migrations(version,name,checksum,applied_at) VALUES("
                    + f"{version},'{escaped_name}','{checksum}',strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n"
                    + "COMMIT;"
                )
                try:
                    connection.executescript(script)
                except Exception as exc:
                    with contextlib.suppress(sqlite3.Error):
                        connection.execute("ROLLBACK")
                    raise MigrationError(f"Failed migration {migration.name}: {exc}") from exc

    @contextlib.contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.execute("COMMIT")
        except Exception:
            with contextlib.suppress(sqlite3.Error):
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def integrity(self) -> dict:
        self.migrate()
        with self.session() as connection:
            sqlite_status = connection.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_keys = [dict(row) for row in connection.execute("PRAGMA foreign_key_check")]
            stream_errors = []
            for row in connection.execute(
                """
                SELECT programme_id, version,
                       COALESCE((SELECT MAX(stream_version) FROM events e WHERE e.programme_id=p.programme_id),0) AS event_version,
                       COALESCE((SELECT COUNT(*) FROM events e WHERE e.programme_id=p.programme_id),0) AS event_count
                FROM programmes p
                """
            ):
                if row["version"] != row["event_version"] or row["event_count"] != row["event_version"]:
                    stream_errors.append(dict(row))
            event_hash_errors = []
            for row in connection.execute("SELECT event_id, payload_json, payload_hash FROM events"):
                try:
                    json.loads(row["payload_json"])
                except json.JSONDecodeError:
                    event_hash_errors.append({"event_id": row["event_id"], "reason": "invalid_json"})
                    continue
                actual = hashlib.sha256(row["payload_json"].encode("utf-8")).hexdigest()
                if actual != row["payload_hash"]:
                    event_hash_errors.append({"event_id": row["event_id"], "reason": "hash_mismatch"})
            return {
                "ok": sqlite_status == "ok" and not foreign_keys and not stream_errors and not event_hash_errors,
                "sqlite": sqlite_status,
                "foreign_key_errors": foreign_keys,
                "stream_errors": stream_errors,
                "event_hash_errors": event_hash_errors,
                "path": str(self.path),
            }
