#!/usr/bin/env python3
"""Read-only structural audit for stale-active memory evidence.

This probe deliberately does not judge arbitrary memory prose. It measures
only explicit lifecycle, edge, continuity-tag, and freshness signals already
stored in Agent-Bridge. Output contains aggregates and one manifest digest;
memory keys and content are never emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time


DEFAULT_DB = os.path.expanduser("~/.local/share/agent-bridge/state.db")
STALE_STATE_DAYS = 14
AGING_CONSTRAINT_DAYS = 45

MEMORY_COLUMNS = {
    "key",
    "kind",
    "tags",
    "created_at",
    "updated_at",
    "last_accessed_at",
    "access_count",
    "status",
    "superseded_by",
    "dedupe_key",
}
EDGE_COLUMNS = {"from_key", "to_key", "edge_type", "created_at"}
LIFECYCLE_EDGE_TYPES = {"supersedes", "invalidates", "corrects"}


def _open_read_only(db_path: str) -> sqlite3.Connection:
    uri = Path(db_path).expanduser().resolve().as_uri() + "?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    db.execute("PRAGMA query_only=ON")
    if db.execute("PRAGMA query_only").fetchone()[0] != 1:
        db.close()
        raise RuntimeError("SQLite query_only could not be enabled")
    return db


def _columns(db: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in db.execute(f"PRAGMA table_info({table})")}


def _require_schema(db: sqlite3.Connection) -> None:
    tables = {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    missing_tables = {"memories", "memory_edges"} - tables
    if missing_tables:
        raise RuntimeError(
            "missing required tables: " + ", ".join(sorted(missing_tables))
        )
    missing_memory = MEMORY_COLUMNS - _columns(db, "memories")
    missing_edges = EDGE_COLUMNS - _columns(db, "memory_edges")
    if missing_memory or missing_edges:
        details = []
        if missing_memory:
            details.append("memories=" + ",".join(sorted(missing_memory)))
        if missing_edges:
            details.append("memory_edges=" + ",".join(sorted(missing_edges)))
        raise RuntimeError("missing required columns: " + "; ".join(details))


def _parse_tags(raw: str) -> tuple[list[str], bool]:
    try:
        parsed = json.loads(raw or "[]")
    except (TypeError, json.JSONDecodeError):
        return [], False
    if not isinstance(parsed, list) or any(not isinstance(v, str) for v in parsed):
        return [], False
    return parsed, True


def _age_band(age_days: int) -> str:
    if age_days < 30:
        return "d14-29"
    if age_days < 60:
        return "d30-59"
    if age_days < 90:
        return "d60-89"
    return "d90+"


def audit(db_path: str, as_of: int | None = None) -> dict:
    if as_of is not None and int(as_of) < 0:
        raise ValueError("as_of must be non-negative")

    db = _open_read_only(db_path)
    db.execute("BEGIN")
    # Establish one read snapshot before fixing the default wall-clock bound.
    # Every later SELECT in this audit therefore observes the same DB state.
    db.execute("SELECT count(*) FROM sqlite_master").fetchone()
    as_of = int(time.time()) if as_of is None else int(as_of)
    start_changes = db.total_changes
    try:
        _require_schema(db)
        memory_rows = db.execute(
            """SELECT key, kind, tags, created_at, updated_at,
                      last_accessed_at, access_count, status,
                      superseded_by, dedupe_key
                 FROM memories
                WHERE created_at <= ?""",
            (as_of,),
        ).fetchall()
        edge_rows = db.execute(
            """SELECT from_key, to_key, edge_type, created_at
                 FROM memory_edges
                WHERE edge_type IN ('supersedes','invalidates','corrects')
                  AND created_at <= ?""",
            (as_of,),
        ).fetchall()

        records: dict[str, dict] = {}
        malformed_tag_rows: set[str] = set()
        for row in memory_rows:
            tags, valid_tags = _parse_tags(row[2])
            if not valid_tags:
                malformed_tag_rows.add(row[0])
            records[row[0]] = {
                "key": row[0],
                "kind": row[1],
                "tags": tags,
                "created_at": int(row[3]),
                "updated_at": int(row[4]),
                "last_accessed_at": int(row[5]),
                "access_count": int(row[6]),
                "status": row[7],
                "superseded_by": row[8],
                "dedupe_key": row[9],
            }

        categories: dict[str, set[str]] = {
            "active_with_superseded_by": set(),
            "active_target_of_supersedes_edge": set(),
            "active_target_of_invalidates_edge": set(),
            "active_declared_supersedes_target": set(),
            "declared_supersedes_missing_edge": set(),
            "active_correction_without_corrects_edge": set(),
            "active_corrected_target": set(),
            "aging_freshness_bound_state": set(),
            "aging_constraint_review": set(),
            "active_duplicate_dedupe_key": set(),
            "malformed_tags": malformed_tag_rows,
        }
        post_signal_access: set[str] = set()

        active = {k: r for k, r in records.items() if r["status"] == "active"}
        for key, rec in active.items():
            if rec["superseded_by"]:
                categories["active_with_superseded_by"].add(key)

        edge_index = {(f, t, typ) for f, t, typ, _ in edge_rows}
        for source_key, target_key, edge_type, edge_created_at in edge_rows:
            target = active.get(target_key)
            if target is None:
                continue
            if edge_type == "supersedes":
                categories["active_target_of_supersedes_edge"].add(target_key)
            elif edge_type == "invalidates":
                categories["active_target_of_invalidates_edge"].add(target_key)
            elif edge_type == "corrects":
                categories["active_corrected_target"].add(target_key)
            if edge_type in {"supersedes", "invalidates"} and target[
                "last_accessed_at"
            ] > int(edge_created_at):
                post_signal_access.add(target_key)

        for source_key, source in active.items():
            for tag in source["tags"]:
                if not tag.startswith("continuity_supersedes:"):
                    continue
                target_key = tag.removeprefix("continuity_supersedes:").strip()
                if not target_key or target_key == source_key:
                    continue
                if target_key in active:
                    categories["active_declared_supersedes_target"].add(target_key)
                if target_key in records and (
                    source_key,
                    target_key,
                    "supersedes",
                ) not in edge_index:
                    categories["declared_supersedes_missing_edge"].add(source_key)

        corrects_sources = {
            source for source, _, edge_type, _ in edge_rows if edge_type == "corrects"
        }
        for key, rec in active.items():
            if (
                rec["kind"] == "feedback"
                and key.startswith("correction:")
                and key not in corrects_sources
            ):
                categories["active_correction_without_corrects_edge"].add(key)

        freshness_age_bands: dict[str, int] = {}
        stale_cutoff = as_of - STALE_STATE_DAYS * 86_400
        constraint_cutoff = as_of - AGING_CONSTRAINT_DAYS * 86_400
        for key, rec in active.items():
            tags = set(rec["tags"])
            freshness_bound = bool(
                {
                    "continuity_freshness_policy:version_bound",
                    "continuity_freshness_policy:project_phase_bound",
                }
                & tags
            )
            if not freshness_bound:
                continue
            reference_ts = max(rec["created_at"], rec["updated_at"])
            is_constraint = "continuity_role:constraint" in tags
            if (
                "continuity_actionability:must_block" in tags
                and not is_constraint
                and reference_ts < stale_cutoff
            ):
                categories["aging_freshness_bound_state"].add(key)
                age_days = max(0, (as_of - reference_ts) // 86_400)
                band = _age_band(age_days)
                freshness_age_bands[band] = freshness_age_bands.get(band, 0) + 1
            elif is_constraint and reference_ts < constraint_cutoff:
                categories["aging_constraint_review"].add(key)

        by_dedupe: dict[str, list[str]] = {}
        for key, rec in active.items():
            if rec["dedupe_key"]:
                by_dedupe.setdefault(rec["dedupe_key"], []).append(key)
        duplicate_groups = 0
        for keys in by_dedupe.values():
            if len(keys) > 1:
                duplicate_groups += 1
                categories["active_duplicate_dedupe_key"].update(keys)

        actionable_category_names = {
            "active_with_superseded_by",
            "active_target_of_supersedes_edge",
            "active_target_of_invalidates_edge",
            "active_declared_supersedes_target",
            "declared_supersedes_missing_edge",
            "active_correction_without_corrects_edge",
            "aging_freshness_bound_state",
            "active_duplicate_dedupe_key",
            "malformed_tags",
        }
        actionable = set().union(
            *(categories[name] for name in actionable_category_names)
        )
        manifest = [
            [category, key]
            for category in sorted(categories)
            for key in sorted(categories[category])
        ]
        manifest_digest = hashlib.sha256(
            json.dumps(manifest, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()

        end_changes = db.total_changes
        result = {
            "schema": "agent_bridge.temporal_truth_drift_audit.v0",
            "mode": "read_only_structural_signals",
            "as_of": as_of,
            "semantic_truth_judgment": False,
            "raw_memory_content_read": False,
            "raw_identifiers_in_output": False,
            "thresholds": {
                "stale_state_days": STALE_STATE_DAYS,
                "aging_constraint_days": AGING_CONSTRAINT_DAYS,
            },
            "population": {
                "memory_rows": len(memory_rows),
                "active_memory_rows": len(active),
                "lifecycle_edges": len(edge_rows),
            },
            "signals": {
                name: len(values) for name, values in sorted(categories.items())
            },
            "signal_details": {
                "active_duplicate_dedupe_groups": duplicate_groups,
                "post_supersede_or_invalidate_access_rows": len(post_signal_access),
                "freshness_bound_age_bands": dict(sorted(freshness_age_bands.items())),
                "unique_actionable_candidate_rows": len(actionable),
                "candidate_manifest_sha256": manifest_digest,
            },
            "verdict": "REVIEW_REQUIRED" if actionable else "CLEAN",
            "authority": "advisory_only_no_automatic_archive_or_supersede",
            "no_write_invariant": {
                "sqlite_uri_mode": "ro",
                "query_only": True,
                "consistent_read_snapshot": True,
                "connection_total_changes_before": start_changes,
                "connection_total_changes_after": end_changes,
                "passed": start_changes == 0 and end_changes == 0,
            },
        }
        return result
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument("--as-of", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = audit(args.db, args.as_of)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("# temporal truth drift structural audit")
        print(f"verdict: {result['verdict']}")
        print(
            "population: "
            f"active={result['population']['active_memory_rows']} "
            f"edges={result['population']['lifecycle_edges']}"
        )
        for name, count in result["signals"].items():
            print(f"  {name}: {count}")
        print(
            "candidate manifest: "
            + result["signal_details"]["candidate_manifest_sha256"]
        )
        print("no-write: PASS" if result["no_write_invariant"]["passed"] else "no-write: FAIL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
