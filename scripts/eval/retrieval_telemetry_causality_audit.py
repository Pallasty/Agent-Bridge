#!/usr/bin/env python3
"""Read-only audit of retrieval telemetry's causal separability.

The audit never infers evaluation traffic from query text, memory keys, or
timing. It requires an explicit ``traffic_class`` column before it can call an
outcome slice causally clean. Output is aggregate-only and never contains a
query or memory identifier.
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
DEFAULT_WINDOW_DAYS = 3
APPLY_MATURATION_SECS = 25_200
AMBIENT_MODE = "bootstrap"
AMBIENT_TOTAL_STAMPS_GATE = 100
AMBIENT_DISTINCT_DAYS_GATE = 7
AMBIENT_CLEAN_STAMPS_GATE = 50
AMBIENT_CLEAN_RANK_MAX = 30

SURFACING_COLUMNS = {
    "memory_key",
    "mode",
    "rank",
    "surfaced_at",
    "used_at",
    "consumed_at",
}
MEMORY_COLUMNS = {"key", "status"}
SEARCH_TRAFFIC_CLASSES = {"organic", "eval"}


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


def _require_schema(db: sqlite3.Connection) -> tuple[set[str], bool]:
    tables = {
        row[0]
        for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    missing_tables = {"memories", "retrieval_surfacing"} - tables
    if missing_tables:
        raise RuntimeError(
            "missing required tables: " + ", ".join(sorted(missing_tables))
        )
    surfacing_columns = _columns(db, "retrieval_surfacing")
    missing_surfacing = SURFACING_COLUMNS - surfacing_columns
    missing_memory = MEMORY_COLUMNS - _columns(db, "memories")
    if missing_surfacing or missing_memory:
        details = []
        if missing_surfacing:
            details.append(
                "retrieval_surfacing=" + ",".join(sorted(missing_surfacing))
            )
        if missing_memory:
            details.append("memories=" + ",".join(sorted(missing_memory)))
        raise RuntimeError("missing required columns: " + "; ".join(details))
    return surfacing_columns, "traffic_class" in surfacing_columns


def _rank_band(rank: int) -> str:
    if rank <= 5:
        return "r00-05"
    if rank <= 15:
        return "r06-15"
    if rank <= 30:
        return "r16-30"
    return "r31+"


def _aggregate_rows(rows: list[dict]) -> dict:
    if not rows:
        return {
            "exposures": 0,
            "used": 0,
            "use_rate_pct": 0.0,
            "distinct_surfacing_days": 0,
            "distinct_used_days": 0,
        }
    used_rows = [row for row in rows if row["used_at"] is not None]
    return {
        "exposures": len(rows),
        "used": len(used_rows),
        "use_rate_pct": round(100.0 * len(used_rows) / len(rows), 2),
        "distinct_surfacing_days": len(
            {row["surfaced_at"] // 86_400 for row in rows}
        ),
        "distinct_used_days": len(
            {row["used_at"] // 86_400 for row in used_rows}
        ),
    }


def _group_candidates(rows: list[dict]) -> tuple[set[str], set[str]]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["memory_key"], []).append(row)
    reinforce = {
        key for key, values in grouped.items() if any(v["used_at"] is not None for v in values)
    }
    decay = {
        key
        for key, values in grouped.items()
        if len(values) >= 2 and all(v["used_at"] is None for v in values)
    }
    return reinforce, decay


def audit(
    db_path: str,
    as_of: int | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> dict:
    if as_of is not None and int(as_of) < 0:
        raise ValueError("as_of must be non-negative")
    if window_days <= 0:
        raise ValueError("window_days must be positive")

    db = _open_read_only(db_path)
    db.execute("BEGIN")
    # Bind active-key membership and surfacing rows to one SQLite snapshot.
    db.execute("SELECT count(*) FROM sqlite_master").fetchone()
    as_of = int(time.time()) if as_of is None else int(as_of)
    start_changes = db.total_changes
    try:
        _, traffic_class_present = _require_schema(db)
        active_keys = {
            row[0]
            for row in db.execute("SELECT key FROM memories WHERE status='active'")
        }
        fields = (
            "memory_key, mode, rank, surfaced_at, used_at, consumed_at"
            + (", traffic_class" if traffic_class_present else "")
        )
        raw_rows = db.execute(
            f"SELECT {fields} FROM retrieval_surfacing WHERE surfaced_at <= ?",
            (as_of,),
        ).fetchall()
        rows = []
        for raw in raw_rows:
            traffic_class = raw[6] if traffic_class_present else None
            if isinstance(traffic_class, str):
                traffic_class = traffic_class.strip().lower() or None
            rows.append(
                {
                    "memory_key": raw[0],
                    "mode": raw[1],
                    "rank": int(raw[2]),
                    "surfaced_at": int(raw[3]),
                    "used_at": (
                        None if raw[4] is None or int(raw[4]) > as_of else int(raw[4])
                    ),
                    "consumed_at": (
                        None if raw[5] is None or int(raw[5]) > as_of else int(raw[5])
                    ),
                    "traffic_class": traffic_class,
                }
            )

        window_start = as_of - window_days * 86_400
        cutoff = as_of - APPLY_MATURATION_SECS
        window_rows = [row for row in rows if row["surfaced_at"] >= window_start]
        window_search_rows = [
            row for row in window_rows if row["mode"] != AMBIENT_MODE
        ]
        mature_pending = [
            row
            for row in rows
            if row["mode"] != AMBIENT_MODE
            and row["consumed_at"] is None
            and row["surfaced_at"] <= cutoff
            and row["memory_key"] in active_keys
        ]

        by_mode: dict[str, dict] = {}
        for mode in sorted({row["mode"] for row in window_rows}):
            by_mode[mode] = _aggregate_rows(
                [row for row in window_rows if row["mode"] == mode]
            )
        rank_bands: dict[str, dict] = {}
        for band in ("r00-05", "r06-15", "r16-30", "r31+"):
            rank_bands[band] = _aggregate_rows(
                [row for row in window_search_rows if _rank_band(row["rank"]) == band]
            )

        invalid_window_labels = [
            row
            for row in window_search_rows
            if row["traffic_class"] not in SEARCH_TRAFFIC_CLASSES
        ]
        invalid_pending_labels = [
            row
            for row in mature_pending
            if row["traffic_class"] not in SEARCH_TRAFFIC_CLASSES
        ]
        traffic_class_counts: dict[str, int] = {}
        if traffic_class_present:
            for row in window_search_rows:
                label = row["traffic_class"] or "unlabeled"
                if label not in SEARCH_TRAFFIC_CLASSES:
                    label = "invalid_or_unlabeled"
                traffic_class_counts[label] = traffic_class_counts.get(label, 0) + 1
        else:
            traffic_class_counts["unobservable"] = len(window_search_rows)

        existing_reinforce, existing_decay = _group_candidates(mature_pending)
        organic_pending = [
            row for row in mature_pending if row["traffic_class"] == "organic"
        ]
        organic_reinforce, organic_decay = _group_candidates(organic_pending)
        eval_pending = [
            row for row in mature_pending if row["traffic_class"] == "eval"
        ]
        eval_keys = {row["memory_key"] for row in eval_pending}
        unknown_pending_keys = {
            row["memory_key"]
            for row in mature_pending
            if row["traffic_class"] not in SEARCH_TRAFFIC_CLASSES
        }
        known_eval_reinforce = existing_reinforce & eval_keys
        known_eval_decay = existing_decay & eval_keys
        possible_eval_reinforce = existing_reinforce & (eval_keys | unknown_pending_keys)
        possible_eval_decay = existing_decay & (eval_keys | unknown_pending_keys)

        candidate_manifest = {
            "existing_decay": sorted(existing_decay),
            "existing_reinforce": sorted(existing_reinforce),
            "known_eval_decay": sorted(known_eval_decay),
            "known_eval_reinforce": sorted(known_eval_reinforce),
            "organic_decay": sorted(organic_decay),
            "organic_reinforce": sorted(organic_reinforce),
        }
        candidate_digest = hashlib.sha256(
            json.dumps(
                candidate_manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True
            ).encode()
        ).hexdigest()

        bootstrap_rows = [row for row in rows if row["mode"] == AMBIENT_MODE]
        bootstrap_used = [row for row in bootstrap_rows if row["used_at"] is not None]
        clean_bootstrap_used = [
            row
            for row in bootstrap_used
            if row["rank"] <= AMBIENT_CLEAN_RANK_MAX
            and not row["memory_key"].startswith("distill_draft_")
        ]
        ambient_conditions = {
            f"total_stamps>={AMBIENT_TOTAL_STAMPS_GATE}": len(bootstrap_used)
            >= AMBIENT_TOTAL_STAMPS_GATE,
            f"distinct_days>={AMBIENT_DISTINCT_DAYS_GATE}": len(
                {row["used_at"] // 86_400 for row in bootstrap_used}
            )
            >= AMBIENT_DISTINCT_DAYS_GATE,
            f"clean_stamps>={AMBIENT_CLEAN_STAMPS_GATE}": len(clean_bootstrap_used)
            >= AMBIENT_CLEAN_STAMPS_GATE,
        }

        if not traffic_class_present:
            verdict = "BLOCKED_NEEDS_TRAFFIC_CLASS"
        elif invalid_window_labels or invalid_pending_labels:
            verdict = "BLOCKED_PARTIAL_TRAFFIC_CLASS"
        else:
            verdict = "READY_FOR_CLEAN_SHADOW"

        end_changes = db.total_changes
        result = {
            "schema": "agent_bridge.retrieval_telemetry_causality_audit.v0",
            "mode": "read_only_aggregate",
            "as_of": as_of,
            "analysis_window_days": window_days,
            "window_start": window_start,
            "apply_maturation_secs": APPLY_MATURATION_SECS,
            "query_text_read": False,
            "query_text_heuristics_allowed": False,
            "raw_identifiers_in_output": False,
            "observability": {
                "traffic_class_column_present": traffic_class_present,
                "accepted_search_traffic_classes": sorted(SEARCH_TRAFFIC_CLASSES),
                "window_search_rows_without_valid_class": len(invalid_window_labels),
                "mature_pending_rows_without_valid_class": len(invalid_pending_labels),
                "causal_separation_ready": verdict == "READY_FOR_CLEAN_SHADOW",
            },
            "window": {
                **_aggregate_rows(window_search_rows),
                "by_mode": by_mode,
                "rank_bands": rank_bands,
                "traffic_class_counts": dict(sorted(traffic_class_counts.items())),
            },
            "mature_pending": {
                "rows": len(mature_pending),
                "distinct_active_memories": len(
                    {row["memory_key"] for row in mature_pending}
                ),
                "existing_reinforce_candidate_memories": len(existing_reinforce),
                "existing_decay_candidate_memories": len(existing_decay),
                "organic_reinforce_candidate_memories": len(organic_reinforce),
                "organic_decay_candidate_memories": len(organic_decay),
                "known_eval_reinforce_candidate_memories": len(known_eval_reinforce),
                "known_eval_decay_candidate_memories": len(known_eval_decay),
                "possible_eval_reinforce_candidate_memories": len(
                    possible_eval_reinforce
                ),
                "possible_eval_decay_candidate_memories": len(possible_eval_decay),
                "candidate_manifest_sha256": candidate_digest,
            },
            "eval_contamination_bounds": {
                "reinforce_candidate_memories_min": len(known_eval_reinforce),
                "reinforce_candidate_memories_max": len(possible_eval_reinforce),
                "decay_candidate_memories_min": len(known_eval_decay),
                "decay_candidate_memories_max": len(possible_eval_decay),
                "identified_exactly": not invalid_pending_labels,
            },
            "ambient_stage2_gate": {
                "total_stamps": len(bootstrap_used),
                "distinct_stamp_days": len(
                    {row["used_at"] // 86_400 for row in bootstrap_used}
                ),
                "clean_stamps": len(clean_bootstrap_used),
                "conditions": ambient_conditions,
                "verdict": "OPEN" if all(ambient_conditions.values()) else "WAIT",
                "stage2_action_authorized": False,
            },
            "verdict": verdict,
            "outcome_apply_authorized": False,
            "authority": "clean_shadow_admission_only",
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
    parser.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = audit(args.db, args.as_of, args.window_days)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("# retrieval telemetry causality audit")
        print(f"verdict: {result['verdict']}")
        print(
            "traffic_class: "
            + ("present" if result["observability"]["traffic_class_column_present"] else "absent")
        )
        print(
            "mature pending: "
            f"rows={result['mature_pending']['rows']} "
            f"decay_candidates={result['mature_pending']['existing_decay_candidate_memories']}"
        )
        print(f"ambient stage2: {result['ambient_stage2_gate']['verdict']}")
        print("no-write: PASS" if result["no_write_invariant"]["passed"] else "no-write: FAIL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
