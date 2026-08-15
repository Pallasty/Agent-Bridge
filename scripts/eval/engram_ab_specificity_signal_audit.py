#!/usr/bin/env python3
"""Read-only preflight for an Agent-Bridge graph-specificity scout.

The audit answers one narrow question: does an already-observed retrieval
target have enough *trusted* local graph structure to justify implementing an
offline clustered-reorganization arm?

It never reads memory content, queries, embeddings, or raw reviewer material.
It opens an explicitly supplied SQLite snapshot as immutable/read-only and
emits aggregate topology metrics only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.engram_ab_specificity_signal_audit.v0"
TRUSTED_EDGE_TYPES = ("cofires", "co_referenced")


class AuditError(RuntimeError):
    """Raised when the supplied snapshot cannot support a trustworthy audit."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _readonly_connection(path: Path) -> sqlite3.Connection:
    uri = f"{path.resolve().as_uri()}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    connection.execute("PRAGMA query_only = ON")
    return connection


def _required_tables(connection: sqlite3.Connection) -> None:
    available = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    required = {"memories", "memory_edges", "memory_coactivation"}
    missing = sorted(required - available)
    if missing:
        raise AuditError(f"missing required tables: {', '.join(missing)}")


def _scope_matches_project(scope: str | None, project_suffix: str) -> bool:
    if not scope:
        return False
    normalized = scope.rstrip("/")
    suffix = project_suffix.strip("/")
    return normalized == suffix or normalized.endswith(f"/{suffix}")


def audit_snapshot(
    db_path: Path,
    target_key: str,
    project_suffix: str,
    *,
    min_trusted_cluster_degree: int = 2,
    min_consolidated_coactivation_degree: int = 2,
) -> dict[str, Any]:
    if not target_key:
        raise AuditError("target key must not be empty")
    if not project_suffix.strip("/"):
        raise AuditError("project suffix must not be empty")
    if min_trusted_cluster_degree < 1:
        raise AuditError("min trusted cluster degree must be positive")
    if min_consolidated_coactivation_degree < 1:
        raise AuditError("min consolidated coactivation degree must be positive")
    if not db_path.is_file():
        raise AuditError(f"snapshot does not exist: {db_path}")

    before_digest = sha256_file(db_path)
    connection = _readonly_connection(db_path)
    try:
        _required_tables(connection)
        quick_check = connection.execute("PRAGMA quick_check(1)").fetchone()
        if not quick_check or quick_check[0] != "ok":
            raise AuditError("snapshot quick_check failed")

        target = connection.execute(
            "SELECT scope, status FROM memories WHERE key = ?",
            (target_key,),
        ).fetchone()
        if target is None:
            raise AuditError("target key is absent from snapshot")
        target_scope, target_status = target
        if target_status != "active":
            raise AuditError(f"target status must be active, got {target_status!r}")

        active_memories = int(
            connection.execute(
                "SELECT COUNT(*) FROM memories WHERE status = 'active'"
            ).fetchone()[0]
        )
        total_edges = int(
            connection.execute("SELECT COUNT(*) FROM memory_edges").fetchone()[0]
        )

        edge_rows = connection.execute(
            """
            SELECT edge_type, COUNT(*)
              FROM memory_edges
             WHERE from_key = ? OR to_key = ?
             GROUP BY edge_type
             ORDER BY edge_type
            """,
            (target_key, target_key),
        ).fetchall()
        edge_type_counts = {str(edge_type): int(count) for edge_type, count in edge_rows}
        trusted_cluster_degree = sum(
            edge_type_counts.get(edge_type, 0) for edge_type in TRUSTED_EDGE_TYPES
        )
        explicit_related_degree = edge_type_counts.get("relates", 0)
        evolved_degree = edge_type_counts.get("evolved", 0)

        evolved_scopes = connection.execute(
            """
            SELECT m.scope
              FROM memory_edges AS e
              LEFT JOIN memories AS m
                ON m.key = CASE
                    WHEN e.from_key = ? THEN e.to_key
                    ELSE e.from_key
                END
             WHERE (e.from_key = ? OR e.to_key = ?)
               AND e.edge_type = 'evolved'
            """,
            (target_key, target_key, target_key),
        ).fetchall()
        same_project_evolved_degree = sum(
            1
            for (scope,) in evolved_scopes
            if _scope_matches_project(scope, project_suffix)
        )
        evolved_scope_purity = (
            same_project_evolved_degree / evolved_degree if evolved_degree else None
        )

        coactivation = connection.execute(
            """
            SELECT COUNT(*),
                   COALESCE(MAX(count), 0),
                   COALESCE(SUM(CASE WHEN consolidated = 1 THEN 1 ELSE 0 END), 0)
              FROM memory_coactivation
             WHERE key_a = ? OR key_b = ?
            """,
            (target_key, target_key),
        ).fetchone()
        coactivation_degree = int(coactivation[0])
        coactivation_max_count = int(coactivation[1])
        consolidated_coactivation_degree = int(coactivation[2])
    finally:
        connection.close()

    after_digest = sha256_file(db_path)
    if after_digest != before_digest:
        raise AuditError("snapshot digest changed during read-only audit")

    trusted_signal_ready = (
        trusted_cluster_degree >= min_trusted_cluster_degree
        or consolidated_coactivation_degree
        >= min_consolidated_coactivation_degree
    )
    status = (
        "READY_FOR_OFFLINE_CLUSTER_SCOUT"
        if trusted_signal_ready
        else "NO_GO_INSUFFICIENT_TRUSTED_CLUSTER_SIGNAL"
    )

    return {
        "schema": SCHEMA,
        "status": status,
        "read_only": True,
        "snapshot": {
            "sha256": before_digest,
            "active_memories": active_memories,
            "total_memory_edges": total_edges,
        },
        "target": {
            "key": target_key,
            "scope": target_scope,
            "status": target_status,
        },
        "metrics": {
            "edge_type_counts": edge_type_counts,
            "trusted_cluster_degree": trusted_cluster_degree,
            "explicit_related_degree": explicit_related_degree,
            "evolved_degree": evolved_degree,
            "same_project_evolved_degree": same_project_evolved_degree,
            "evolved_scope_purity": evolved_scope_purity,
            "coactivation_degree": coactivation_degree,
            "coactivation_max_count": coactivation_max_count,
            "consolidated_coactivation_degree": consolidated_coactivation_degree,
        },
        "thresholds": {
            "min_trusted_cluster_degree": min_trusted_cluster_degree,
            "min_consolidated_coactivation_degree": (
                min_consolidated_coactivation_degree
            ),
            "trusted_edge_types": list(TRUSTED_EDGE_TYPES),
        },
        "authority": {
            "candidate_implementation": False,
            "retrieval_mutation": False,
            "memory_or_graph_writes": False,
            "integration": False,
            "deployment": False,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--target-key", required=True)
    parser.add_argument(
        "--project-suffix",
        default="agent-bridge",
        help="Path suffix accepted as the target project across host aliases.",
    )
    parser.add_argument("--pretty", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = audit_snapshot(args.db, args.target_key, args.project_suffix)
    except (AuditError, OSError, sqlite3.Error) as error:
        print(
            json.dumps(
                {
                    "schema": SCHEMA,
                    "status": "AUDIT_ERROR",
                    "read_only": True,
                    "error": str(error),
                },
                sort_keys=True,
            )
        )
        return 2

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2 if args.pretty else None,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
