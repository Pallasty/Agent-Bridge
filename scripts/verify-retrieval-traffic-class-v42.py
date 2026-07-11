#!/usr/bin/env python3
"""Copied-DB acceptance gate for retrieval traffic provenance schema v42.

The source database is opened read-only and copied with SQLite's online backup
API into a verified-private temporary directory. Standard output is aggregate
only: query text, memory keys, MCP payloads, and temporary paths are omitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import tempfile
import time
from typing import Any


OLD_SURFACING_FIELDS = (
    "id",
    "memory_key",
    "query",
    "mode",
    "rank",
    "surfaced_at",
    "used_at",
    "consumed_at",
)
EXPECTED_CLASSES = {"unknown", "organic", "eval"}


class GateError(RuntimeError):
    pass


def sqlite_backup(source: Path, destination: Path) -> None:
    source_uri = source.resolve().as_uri() + "?mode=ro"
    source_db = sqlite3.connect(source_uri, uri=True)
    destination_db = sqlite3.connect(destination)
    try:
        source_db.execute("PRAGMA query_only=ON")
        source_db.backup(destination_db)
    finally:
        destination_db.close()
        source_db.close()


def private_tempdir(parent: Path | None, keep: bool) -> tuple[Path, bool]:
    base = None if parent is None else str(parent)
    path = Path(tempfile.mkdtemp(prefix="ab-v42-traffic-", dir=base))
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        shutil.rmtree(path, ignore_errors=True)
        raise GateError(
            f"temporary directory permissions are not private (mode {mode:04o})"
        )
    return path, keep


def schema_version(db_path: Path) -> str:
    db = sqlite3.connect(db_path)
    try:
        row = db.execute(
            "SELECT value FROM schema_meta WHERE key='version'"
        ).fetchone()
        if row is None:
            raise GateError("schema_meta.version is missing")
        return str(row[0])
    finally:
        db.close()


def old_field_digest(db_path: Path) -> tuple[int, int, str]:
    db = sqlite3.connect(db_path)
    digest = hashlib.sha256()
    count = 0
    max_id = 0
    try:
        fields = ", ".join(OLD_SURFACING_FIELDS)
        for row in db.execute(
            f"SELECT {fields} FROM retrieval_surfacing ORDER BY id"
        ):
            count += 1
            max_id = max(max_id, int(row[0]))
            digest.update(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            digest.update(b"\n")
    finally:
        db.close()
    return count, max_id, digest.hexdigest()


def binary_identity(binary: Path) -> str:
    completed = subprocess.run(
        [str(binary), "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    identity = "\n".join(
        part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
    )
    if completed.returncode != 0 or not identity:
        raise GateError("could not observe binary identity")
    return identity


class McpClient:
    def __init__(
        self,
        binary: Path,
        db_path: Path,
        stderr_path: Path,
        traffic_class: str | None,
    ) -> None:
        env = os.environ.copy()
        env.update(
            {
                "AGENT_BRIDGE_DB": str(db_path),
                "AGENT_BRIDGE_TOOL_PROFILE": "all",
                "AGENT_BRIDGE_TOOLSET": "all",
                "AGENT_BRIDGE_OUTCOME_COLLECTOR": "1",
                "AGENT_BRIDGE_RETRIEVAL_OUTCOME_APPLY": "0",
                "AGENT_BRIDGE_EMBED_BACKEND": "hash",
                "AGENT_BRIDGE_DIM_GUARD_STRICT": "0",
                "AB_BOOTSTRAP_SURFACING_DISABLE": "0",
                "RUST_LOG": "info",
            }
        )
        if traffic_class is None:
            env.pop("AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS", None)
        else:
            env["AGENT_BRIDGE_RETRIEVAL_TRAFFIC_CLASS"] = traffic_class
        self._stderr = stderr_path.open("wb")
        self._process = subprocess.Popen(
            [str(binary), "mcp"],
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self._stderr,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        if self._process.stdin is None or self._process.stdout is None:
            raise GateError("failed to open MCP stdio")
        self._next_id = 1
        self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "v42-copied-db-gate", "version": "1"},
            },
        )
        self._send(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
        )

    def _send(self, packet: dict[str, Any]) -> None:
        assert self._process.stdin is not None
        self._process.stdin.write(
            json.dumps(packet, ensure_ascii=False, separators=(",", ":")) + "\n"
        )
        self._process.stdin.flush()

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            }
        )
        assert self._process.stdout is not None
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            line = self._process.stdout.readline()
            if not line:
                raise GateError("MCP process exited before replying")
            try:
                packet = json.loads(line)
            except json.JSONDecodeError:
                continue
            if packet.get("id") != request_id:
                continue
            if "error" in packet:
                raise GateError("MCP request returned an error")
            result = packet.get("result")
            if not isinstance(result, dict):
                raise GateError("MCP response did not contain an object result")
            return result
        raise GateError("MCP request timed out")

    def close(self) -> None:
        try:
            if self._process.stdin is not None and not self._process.stdin.closed:
                self._process.stdin.close()
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._process.terminate()
            self._process.wait(timeout=5)
        finally:
            self._stderr.close()


def migrate_only(binary: Path, db_path: Path, stderr_path: Path) -> None:
    client = McpClient(binary, db_path, stderr_path, "eval")
    client.close()


def query_candidates(path: Path) -> list[str]:
    packet = json.loads(path.read_text(encoding="utf-8"))
    queries = [
        row.get("query")
        for row in packet.get("pairs", [])
        if isinstance(row, dict) and isinstance(row.get("query"), str)
    ]
    if not queries:
        raise GateError("retrieval query fixture contains no usable queries")
    return queries


def max_surfacing_id(db_path: Path) -> int:
    db = sqlite3.connect(db_path)
    try:
        return int(
            db.execute("SELECT coalesce(max(id), 0) FROM retrieval_surfacing")
            .fetchone()[0]
        )
    finally:
        db.close()


def new_row_summary(db_path: Path, after_id: int) -> dict[str, Any]:
    db = sqlite3.connect(db_path)
    try:
        rows = db.execute(
            "SELECT mode, traffic_class FROM retrieval_surfacing WHERE id > ?",
            (after_id,),
        ).fetchall()
    finally:
        db.close()
    classes: dict[str, int] = {}
    modes: dict[str, int] = {}
    for mode, traffic_class in rows:
        classes[str(traffic_class)] = classes.get(str(traffic_class), 0) + 1
        modes[str(mode)] = modes.get(str(mode), 0) + 1
    return {
        "rows": len(rows),
        "traffic_class_counts": dict(sorted(classes.items())),
        "mode_counts": dict(sorted(modes.items())),
    }


def writer_smoke(
    *,
    binary: Path,
    db_path: Path,
    stderr_path: Path,
    traffic_class: str | None,
    expected_class: str,
    queries: list[str],
    tool: str,
    scope_cwd: str,
) -> dict[str, Any]:
    before_id = max_surfacing_id(db_path)
    client = McpClient(binary, db_path, stderr_path, traffic_class)
    summary: dict[str, Any] | None = None
    try:
        for query in queries:
            arguments: dict[str, Any]
            if tool == "memory_search":
                arguments = {"query": query, "mode": "fts", "limit": 10}
            else:
                arguments = {
                    "cwd": scope_cwd,
                    "query": query,
                    "limit": 10,
                    "frontend": "claude-code",
                }
            client.request("tools/call", {"name": tool, "arguments": arguments})
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                summary = new_row_summary(db_path, before_id)
                if summary["rows"]:
                    break
                time.sleep(0.05)
            if summary is not None and summary["rows"]:
                break
    finally:
        client.close()
    if summary is None or summary["rows"] == 0:
        raise GateError(f"{tool} produced no retrieval_surfacing rows")
    if summary["traffic_class_counts"] != {expected_class: summary["rows"]}:
        raise GateError(f"{tool} persisted an unexpected traffic class")
    if tool == "session_bootstrap" and summary["mode_counts"] != {
        "bootstrap": summary["rows"]
    }:
        raise GateError("session_bootstrap persisted a non-bootstrap mode")
    return summary


def validate_migration(
    db_path: Path,
    expected_count: int,
    expected_max_id: int,
    expected_digest: str,
) -> dict[str, Any]:
    count, max_id, digest = old_field_digest(db_path)
    db = sqlite3.connect(db_path)
    try:
        version = schema_version(db_path)
        class_counts = {
            str(label): int(rows)
            for label, rows in db.execute(
                "SELECT traffic_class, count(*) FROM retrieval_surfacing "
                "GROUP BY traffic_class"
            )
        }
        column_rows = [
            row
            for row in db.execute("PRAGMA table_info(retrieval_surfacing)")
            if row[1] == "traffic_class"
        ]
        index_columns = [
            row[2]
            for row in db.execute(
                "PRAGMA index_info(idx_retrieval_surfacing_traffic_at)"
            )
        ]
        table_sql = db.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type='table' AND name='retrieval_surfacing'"
        ).fetchone()[0]
    finally:
        db.close()
    if version != "42":
        raise GateError("candidate did not migrate the copied DB to schema 42")
    if (count, max_id, digest) != (
        expected_count,
        expected_max_id,
        expected_digest,
    ):
        raise GateError("migration changed pre-v42 retrieval surfacing fields")
    if class_counts != ({"unknown": count} if count else {}):
        raise GateError("historical rows were not exclusively labelled unknown")
    if len(column_rows) != 1 or int(column_rows[0][3]) != 1:
        raise GateError("traffic_class column is missing or nullable")
    normalized_sql = " ".join(str(table_sql).lower().split())
    if "check (traffic_class in ('unknown', 'organic', 'eval'))" not in normalized_sql:
        raise GateError("traffic_class CHECK constraint is missing")
    if index_columns != ["traffic_class", "surfaced_at"]:
        raise GateError("traffic class index has unexpected columns")
    return {
        "schema_version": version,
        "rows_preserved": True,
        "old_field_digest_preserved": True,
        "historical_traffic_class_counts": class_counts,
        "column_not_null": True,
        "check_constraint_present": True,
        "index_columns": index_columns,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--candidate-bin", required=True, type=Path)
    parser.add_argument("--old-bin", required=True, type=Path)
    parser.add_argument("--source-db", required=True, type=Path)
    parser.add_argument(
        "--query-fixture",
        type=Path,
        default=Path(__file__).resolve().parent
        / "eval"
        / "fixtures"
        / "retrieval_pairs.json",
    )
    parser.add_argument(
        "--scope-cwd", default="/Data/CascadeProjects/agent-bridge"
    )
    parser.add_argument("--temp-parent", type=Path)
    parser.add_argument("--keep-temp", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    for path, label in (
        (args.candidate_bin, "candidate binary"),
        (args.old_bin, "old binary"),
        (args.source_db, "source DB"),
        (args.query_fixture, "query fixture"),
    ):
        if not path.is_file():
            raise GateError(f"{label} does not exist")
    for path, label in (
        (args.candidate_bin, "candidate binary"),
        (args.old_bin, "old binary"),
    ):
        if not os.access(path, os.X_OK):
            raise GateError(f"{label} is not executable")

    temp_parent = args.temp_parent
    if temp_parent is None:
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
        temp_parent = Path(runtime_dir) if runtime_dir else Path("/tmp")
    temp_dir, keep = private_tempdir(temp_parent, args.keep_temp)
    try:
        source_copy = temp_dir / "source-v41.db"
        sqlite_backup(args.source_db, source_copy)
        source_version = schema_version(source_copy)
        if source_version != "41":
            raise GateError(
                f"source copied DB must be schema 41 for this migration gate, got {source_version}"
            )
        source_count, source_max_id, source_digest = old_field_digest(source_copy)

        migrated = temp_dir / "migrated-v42.db"
        sqlite_backup(source_copy, migrated)
        migrate_only(args.candidate_bin, migrated, temp_dir / "migrate.stderr")
        migration = validate_migration(
            migrated, source_count, source_max_id, source_digest
        )
        queries = query_candidates(args.query_fixture)

        smoke_specs = (
            ("organic_search", "organic", "organic", "memory_search", args.candidate_bin),
            ("eval_search", "eval", "eval", "memory_search", args.candidate_bin),
            ("unset_search", None, "unknown", "memory_search", args.candidate_bin),
            ("invalid_search", "production", "unknown", "memory_search", args.candidate_bin),
            ("eval_bootstrap", "eval", "eval", "session_bootstrap", args.candidate_bin),
            ("v41_compat", "organic", "unknown", "memory_search", args.old_bin),
        )
        smokes: dict[str, dict[str, Any]] = {}
        for label, traffic_class, expected, tool, binary in smoke_specs:
            smoke_db = temp_dir / f"{label}.db"
            sqlite_backup(migrated, smoke_db)
            smokes[label] = writer_smoke(
                binary=binary,
                db_path=smoke_db,
                stderr_path=temp_dir / f"{label}.stderr",
                traffic_class=traffic_class,
                expected_class=expected,
                queries=queries,
                tool=tool,
                scope_cwd=args.scope_cwd,
            )

        result = {
            "schema": "agent_bridge.retrieval_traffic_class_v42_copied_db_gate.v0",
            "source_schema_version": source_version,
            "source_retrieval_rows": source_count,
            "source_old_fields_sha256": source_digest,
            "candidate_identity": binary_identity(args.candidate_bin),
            "old_binary_identity": binary_identity(args.old_bin),
            "migration": migration,
            "writer_smokes": smokes,
            "raw_queries_in_output": False,
            "raw_memory_identifiers_in_output": False,
            "source_db_opened_read_only": True,
            "private_temp_directory_verified": True,
            "outcome_apply_authorized": False,
            "verdict": "PASS",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    finally:
        if not keep:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GateError as exc:
        raise SystemExit(f"FAIL: {exc}") from exc
