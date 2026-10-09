#!/usr/bin/env python3
"""Audit the public PGRA Hermes profile distribution using only the standard library."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


REQUIRED_FILES = {
    "distribution.yaml",
    "SOUL.md",
    "config.yaml",
    ".env.EXAMPLE",
    "AGENTS.md",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "skills/pgra-research/SKILL.md",
    "docs/PGRA_DESIGN.md",
    "docs/IMPLEMENTATION_PLAN.md",
    "docs/HERMES_DEFAULT_PROMPT.md",
    "docs/HANDOFF_BRIEF.md",
    "docs/CLI_REFERENCE.md",
    "docs/CONSUMER_HARDENING_PLAN.md",
    "docs/BACKUP_AND_RECOVERY.md",
    "runtime/pgra/__init__.py",
    "runtime/pgra/db.py",
    "runtime/pgra/service.py",
    "runtime/pgra/evaluation.py",
    "runtime/pgra/cli.py",
    "runtime/pgra/migrations/001_initial.sql",
    "runtime/pgra/migrations/002_consumer_hardening.sql",
    "pgra.py",
    "tests/test_cross_session_cli.py",
    "tests/test_state_engine.py",
    "tests/test_evidence_and_beliefs.py",
    "tests/test_evaluation.py",
    "tests/test_full_cli_workflow.py",
    "tests/test_consumer_hardening.py",
}

REQUIRED_OWNED = {
    "AGENTS.md",
    "CHANGELOG.md",
    "LICENSE",
    "SOUL.md",
    "config.yaml",
    ".env.EXAMPLE",
    "skills",
    "docs",
    "runtime/pgra/__init__.py",
    "runtime/pgra/cli.py",
    "runtime/pgra/db.py",
    "runtime/pgra/evaluation.py",
    "runtime/pgra/service.py",
    "runtime/pgra/migrations/001_initial.sql",
    "runtime/pgra/migrations/002_consumer_hardening.sql",
    "pgra.py",
    "tests/test_cross_session_cli.py",
    "tests/test_evaluation.py",
    "tests/test_evidence_and_beliefs.py",
    "tests/test_state_engine.py",
    "tests/test_full_cli_workflow.py",
    "tests/test_consumer_hardening.py",
}

PRIVATE_PARTS = {".pgra", ".hermes", "sessions", "memories", "cookies", "data", "runs", "research-state"}
PRIVATE_SUFFIXES = {".sqlite", ".sqlite3", ".db", ".db-wal", ".db-shm", ".db-journal", ".log"}
SECRET_PATTERNS = (
    re.compile(r"gho_[A-Za-z0-9_]{16,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{16,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
)
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\((?!https?://|mailto:|#)([^)]+)\)")


def tracked_files(root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return [p.relative_to(root) for p in root.rglob("*") if p.is_file() and ".git" not in p.parts]
    return [Path(line) for line in result.stdout.splitlines() if line.strip()]


def top_level_scalar(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*[\"']?([^\n\"']+)[\"']?\s*$", text)
    return match.group(1).strip() if match else None


def yaml_list(text: str, key: str) -> list[str]:
    lines = text.splitlines()
    values: list[str] = []
    active = False
    for line in lines:
        if re.match(rf"^{re.escape(key)}:\s*$", line):
            active = True
            continue
        if active and re.match(r"^[A-Za-z_][\w-]*:\s*", line):
            break
        if active:
            match = re.match(r"^\s+-\s+(.+?)\s*$", line)
            if match:
                values.append(match.group(1).strip("\"'"))
    return values


def validate_manifest(root: Path) -> list[str]:
    errors: list[str] = []
    path = root / "distribution.yaml"
    if not path.is_file():
        return ["missing distribution.yaml"]
    text = path.read_text(encoding="utf-8-sig")
    if top_level_scalar(text, "name") != "pgra":
        errors.append("distribution name must be pgra")
    version = top_level_scalar(text, "version") or ""
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        errors.append("distribution version must be semantic major.minor.patch")
    requirement = top_level_scalar(text, "hermes_requires") or ""
    if not re.fullmatch(r">=\d+\.\d+\.\d+", requirement):
        errors.append("hermes_requires must be an explicit >= semantic version")
    owned = set(yaml_list(text, "distribution_owned"))
    missing_owned = REQUIRED_OWNED - owned
    if missing_owned:
        errors.append(f"distribution_owned missing: {sorted(missing_owned)}")
    if "cron" in owned or (root / "cron").exists():
        errors.append("cron must not be shipped by default")
    return errors


def validate_skill(root: Path) -> list[str]:
    errors: list[str] = []
    path = root / "skills/pgra-research/SKILL.md"
    if not path.is_file():
        return ["missing PGRA skill"]
    text = path.read_text(encoding="utf-8-sig")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        errors.append("PGRA skill must have YAML frontmatter")
        return errors
    frontmatter = text.split("---", 2)[1]
    for key in ("name", "description", "version", "author"):
        if not re.search(rf"(?m)^{key}:\s*\S", frontmatter):
            errors.append(f"PGRA skill frontmatter missing {key}")
    if top_level_scalar(frontmatter, "name") != "pgra-research":
        errors.append("PGRA skill name must be pgra-research")
    return errors


def validate_env_example(root: Path) -> list[str]:
    errors: list[str] = []
    path = root / ".env.EXAMPLE"
    if not path.is_file():
        return ["missing .env.EXAMPLE"]
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if value.strip():
            errors.append(f".env.EXAMPLE:{number} must not contain a value for {name}")
    return errors


def validate_version_consistency(root: Path) -> list[str]:
    manifest = (root / "distribution.yaml").read_text(encoding="utf-8-sig")
    version = top_level_scalar(manifest, "version")
    if not version:
        return ["distribution version is unavailable"]
    runtime = (root / "runtime/pgra/__init__.py").read_text(encoding="utf-8-sig")
    skill = (root / "skills/pgra-research/SKILL.md").read_text(encoding="utf-8-sig")
    errors = []
    if f'__version__ = "{version}"' not in runtime:
        errors.append("runtime version does not match distribution version")
    if top_level_scalar(skill.split("---", 2)[1], "version") != version:
        errors.append("skill version does not match distribution version")
    return errors


def validate_public_files(root: Path) -> list[str]:
    errors: list[str] = []
    files = tracked_files(root)
    normalized = {p.as_posix() for p in files}
    missing = REQUIRED_FILES - normalized
    if missing:
        errors.append(f"required files missing from repository: {sorted(missing)}")

    for rel in files:
        lowered_parts = {part.lower() for part in rel.parts}
        name = rel.name.lower()
        if lowered_parts & PRIVATE_PARTS or any(name.endswith(suffix) for suffix in PRIVATE_SUFFIXES):
            errors.append(f"private/runtime path is tracked: {rel.as_posix()}")
            continue
        path = root / rel
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"potential secret in {rel.as_posix()}: {pattern.pattern}")
    return errors


def validate_markdown_links(root: Path) -> list[str]:
    errors: list[str] = []
    for path in root.rglob("*.md"):
        if ".git" in path.parts:
            continue
        text = path.read_text(encoding="utf-8-sig")
        for match in MARKDOWN_LINK.finditer(text):
            raw = match.group(1).split("#", 1)[0].strip()
            if not raw or raw.startswith(("/", "<")):
                continue
            if not (path.parent / raw).resolve().exists():
                errors.append(f"broken local link: {path.relative_to(root).as_posix()} -> {raw}")
    return errors


def audit(root: Path) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_manifest(root))
    errors.extend(validate_skill(root))
    errors.extend(validate_env_example(root))
    errors.extend(validate_version_consistency(root))
    errors.extend(validate_public_files(root))
    errors.extend(validate_markdown_links(root))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    errors = audit(root)
    result = {"ok": not errors, "root": str(root), "errors": errors}
    if args.json:
        print(json.dumps(result, indent=2))
    elif errors:
        print("PGRA distribution audit: FAIL")
        for error in errors:
            print(f"- {error}")
    else:
        print("PGRA distribution audit: PASS")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
