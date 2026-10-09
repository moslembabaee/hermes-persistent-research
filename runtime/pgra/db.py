from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Iterator


PROJECTION_TABLES = (
    "hypotheses",
    "claims",
    "sources",
    "source_snapshots",
    "source_lineage",
    "evidence_items",
    "belief_revisions",
    "experiments",
    "research_cycles",
    "checkpoints",
    "evaluation_runs",
)

PROJECTION_DELETE_ORDER = (
    "belief_revisions",
    "evidence_items",
    "source_lineage",
    "source_snapshots",
    "experiments",
    "checkpoints",
    "research_cycles",
    "claims",
    "hypotheses",
    "sources",
    "evaluation_runs",
)


def canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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
        self._ensure_projection_baselines()

    def _table_rows(self, connection: sqlite3.Connection, table: str, programme_id: str) -> list[dict]:
        if table == "source_snapshots":
            query = """SELECT ss.* FROM source_snapshots ss
                       JOIN sources s ON s.source_id=ss.source_id
                       WHERE s.programme_id=? ORDER BY ss.snapshot_id"""
        else:
            query = f"SELECT * FROM {table} WHERE programme_id=? ORDER BY rowid"
        return [dict(row) for row in connection.execute(query, (programme_id,))]

    def capture_projection(
        self,
        connection: sqlite3.Connection,
        programme_id: str,
        *,
        version: int | None = None,
        updated_at: str | None = None,
    ) -> dict:
        programme = connection.execute(
            "SELECT * FROM programmes WHERE programme_id=?", (programme_id,)
        ).fetchone()
        if programme is None:
            raise MigrationError(f"Programme projection not found: {programme_id}")
        programme_data = dict(programme)
        if version is not None:
            programme_data["version"] = version
        if updated_at is not None:
            programme_data["updated_at"] = updated_at
        return {
            "programme": programme_data,
            "tables": {
                table: self._table_rows(connection, table, programme_id)
                for table in PROJECTION_TABLES
            },
        }

    def _ensure_projection_baselines(self) -> None:
        """Upgrade pre-0.3 streams with one complete, rebuildable baseline event."""
        with self.session() as connection:
            programmes = connection.execute("SELECT programme_id, version FROM programmes").fetchall()
            for programme in programmes:
                latest = connection.execute(
                    "SELECT payload_json FROM events WHERE programme_id=? ORDER BY stream_version DESC LIMIT 1",
                    (programme["programme_id"],),
                ).fetchone()
                if latest is None:
                    continue
                try:
                    payload = json.loads(latest["payload_json"])
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict) and "_projection" in payload:
                    continue

                connection.execute("BEGIN IMMEDIATE")
                try:
                    current = connection.execute(
                        "SELECT version FROM programmes WHERE programme_id=?", (programme["programme_id"],)
                    ).fetchone()
                    version = current["version"] + 1
                    occurred_at = connection.execute(
                        "SELECT strftime('%Y-%m-%dT%H:%M:%fZ','now')"
                    ).fetchone()[0]
                    connection.execute(
                        "UPDATE programmes SET version=?, updated_at=? WHERE programme_id=?",
                        (version, occurred_at, programme["programme_id"]),
                    )
                    projection = self.capture_projection(connection, programme["programme_id"])
                    body = canonical_json({
                        "reason": "v0.3 projection baseline",
                        "_projection": projection,
                    })
                    event_id = f"evt_baseline_{hashlib.sha256((programme['programme_id'] + str(version)).encode()).hexdigest()[:24]}"
                    connection.execute(
                        """INSERT INTO events(event_id,programme_id,stream_version,event_type,occurred_at,actor,
                           schema_version,payload_json,payload_hash)
                           VALUES(?,?,?,?,?,?,2,?,?)""",
                        (
                            event_id,
                            programme["programme_id"],
                            version,
                            "ProjectionBaselineCaptured",
                            occurred_at,
                            "migration",
                            body,
                            hashlib.sha256(body.encode("utf-8")).hexdigest(),
                        ),
                    )
                    connection.execute("COMMIT")
                except Exception:
                    with contextlib.suppress(sqlite3.Error):
                        connection.execute("ROLLBACK")
                    raise

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
            artifact_hash_errors = []
            snapshot_columns = {row[1] for row in connection.execute("PRAGMA table_info(source_snapshots)")}
            if "artifact_path" in snapshot_columns:
                for row in connection.execute(
                    "SELECT snapshot_id,artifact_path,content_hash FROM source_snapshots WHERE artifact_path IS NOT NULL"
                ):
                    artifact = Path(row["artifact_path"]).expanduser()
                    if not artifact.is_absolute():
                        artifact = self.path.parent / artifact
                    if not artifact.is_file():
                        artifact_hash_errors.append({"snapshot_id": row["snapshot_id"], "reason": "artifact_missing"})
                        continue
                    actual = hashlib.sha256(artifact.read_bytes()).hexdigest()
                    if actual.lower() != (row["content_hash"] or "").lower():
                        artifact_hash_errors.append({"snapshot_id": row["snapshot_id"], "reason": "artifact_hash_mismatch"})
            projection = self.projection_status(_connection=connection)
            return {
                "ok": sqlite_status == "ok" and not foreign_keys and not stream_errors and not event_hash_errors
                and not artifact_hash_errors and projection["ok"],
                "sqlite": sqlite_status,
                "foreign_key_errors": foreign_keys,
                "stream_errors": stream_errors,
                "event_hash_errors": event_hash_errors,
                "artifact_hash_errors": artifact_hash_errors,
                "projection": projection,
                "path": str(self.path),
            }

    def _latest_projection(self, connection: sqlite3.Connection, programme_id: str) -> dict:
        rows = connection.execute(
            "SELECT event_id, stream_version, payload_json FROM events WHERE programme_id=? ORDER BY stream_version DESC",
            (programme_id,),
        )
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except json.JSONDecodeError:
                continue
            projection = payload.get("_projection") if isinstance(payload, dict) else None
            if projection:
                return {
                    "event_id": row["event_id"],
                    "stream_version": row["stream_version"],
                    "projection": projection,
                }
        raise MigrationError(f"No rebuildable projection event for programme: {programme_id}")

    def projection_status(self, *, _connection: sqlite3.Connection | None = None) -> dict:
        if _connection is None:
            self.migrate()
            with self.session() as connection:
                return self.projection_status(_connection=connection)
        connection = _connection
        results = []
        for row in connection.execute("SELECT programme_id, slug FROM programmes ORDER BY slug"):
            try:
                latest = self._latest_projection(connection, row["programme_id"])
            except MigrationError as exc:
                results.append({
                    "programme_id": row["programme_id"],
                    "slug": row["slug"],
                    "matches": False,
                    "error": str(exc),
                })
                continue
            actual = self.capture_projection(connection, row["programme_id"])
            expected = latest["projection"]
            matches = canonical_json(actual) == canonical_json(expected)
            results.append({
                "programme_id": row["programme_id"],
                "slug": row["slug"],
                "event_id": latest["event_id"],
                "stream_version": latest["stream_version"],
                "matches": matches,
            })
        return {"ok": all(item["matches"] for item in results), "programmes": results}

    def rebuild_projection(self, identifier: str) -> dict:
        self.migrate()
        with self.transaction() as connection:
            programme = connection.execute(
                "SELECT * FROM programmes WHERE programme_id=? OR slug=?", (identifier, identifier)
            ).fetchone()
            if programme is None:
                raise MigrationError(f"Programme not found: {identifier}")
            programme_id = programme["programme_id"]
            latest = self._latest_projection(connection, programme_id)
            state = latest["projection"]
            for table in PROJECTION_DELETE_ORDER:
                if table == "source_snapshots":
                    connection.execute(
                        "DELETE FROM source_snapshots WHERE source_id IN (SELECT source_id FROM sources WHERE programme_id=?)",
                        (programme_id,),
                    )
                else:
                    connection.execute(f"DELETE FROM {table} WHERE programme_id=?", (programme_id,))

            saved_programme = state["programme"]
            columns = [column for column in saved_programme if column != "programme_id"]
            connection.execute(
                f"UPDATE programmes SET {','.join(f'{column}=?' for column in columns)} WHERE programme_id=?",
                (*[saved_programme[column] for column in columns], programme_id),
            )
            for table in PROJECTION_TABLES:
                for item in state["tables"].get(table, []):
                    columns = list(item)
                    connection.execute(
                        f"INSERT INTO {table}({','.join(columns)}) VALUES({','.join('?' for _ in columns)})",
                        tuple(item[column] for column in columns),
                    )
            return {
                "ok": True,
                "programme_id": programme_id,
                "restored_from_event": latest["event_id"],
                "stream_version": latest["stream_version"],
            }

    def backup(self, destination: Path | str) -> dict:
        self.migrate()
        destination = Path(destination).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination == self.path:
            raise MigrationError("Backup destination must differ from the active database")
        with contextlib.closing(self.connect()) as source, contextlib.closing(sqlite3.connect(destination)) as target:
            source.backup(target)
        with contextlib.closing(sqlite3.connect(destination)) as check:
            status = check.execute("PRAGMA integrity_check").fetchone()[0]
        if status != "ok":
            destination.unlink(missing_ok=True)
            raise MigrationError(f"Backup integrity check failed: {status}")
        return {"ok": True, "source": str(self.path), "backup": str(destination), "sqlite": status}

    def restore(self, source: Path | str) -> dict:
        source = Path(source).expanduser().resolve()
        if not source.is_file():
            raise MigrationError(f"Backup does not exist: {source}")
        with contextlib.closing(sqlite3.connect(source)) as check:
            status = check.execute("PRAGMA integrity_check").fetchone()[0]
        if status != "ok":
            raise MigrationError(f"Backup integrity check failed: {status}")
        safety_copy = self.path.with_suffix(self.path.suffix + ".before-restore")
        if self.path.exists():
            self.backup(safety_copy)
        with contextlib.closing(sqlite3.connect(source)) as backup_connection, contextlib.closing(sqlite3.connect(self.path)) as target:
            backup_connection.backup(target)
        self.migrate()
        return {
            "ok": True,
            "database": str(self.path),
            "restored_from": str(source),
            "safety_backup": str(safety_copy) if safety_copy.exists() else None,
        }
