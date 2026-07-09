#!/usr/bin/env python3
"""Validate a no-write StructMemEval -> Agent-Bridge projection contract.

This script does not import StructMemEval, does not run a benchmark, does not
call an LLM, and does not write AB memory. It validates synthetic case JSON,
builds temporary in-memory AB-like projection records/edges, and emits a compact
summary suitable for review packets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import urllib.request
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.structmemeval_adapter_contract_impl.v0"
SOURCE_HEAD = "64d2c9b242deb394e3ef94a318868a55261e141b"
DEFAULT_CASES = [
    (
        "tree_based",
        "https://raw.githubusercontent.com/yandex-research/StructMemEval/"
        f"{SOURCE_HEAD}/benchmark/data/tree_based/big_bench/graph_0_trimmed_10_with_path_1.json",
    ),
    (
        "state_machine_location",
        "https://raw.githubusercontent.com/yandex-research/StructMemEval/"
        f"{SOURCE_HEAD}/benchmark/data/state_machine_location/big_bench/static_001.json",
    ),
    (
        "accounting",
        "https://raw.githubusercontent.com/yandex-research/StructMemEval/"
        f"{SOURCE_HEAD}/benchmark/data/accounting/debt_tracker_10_1.json",
    ),
]
COUNT_TABLES = ["memories", "memory_edges", "semantic_events"]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def parse_case_arg(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        fail(f"--case must use family=path_or_url, got {raw!r}")
    family, source = raw.split("=", 1)
    family = family.strip()
    source = source.strip()
    if not family or not source:
        fail(f"--case must use non-empty family and source, got {raw!r}")
    if not re.match(r"^[a-zA-Z0-9_.-]+$", family):
        fail(f"invalid family {family!r}")
    return family, source


def load_source(source: str, allow_other_url: bool) -> tuple[bytes, str]:
    if source.startswith("http://"):
        fail("http URLs are refused; use https")
    if source.startswith("https://"):
        expected_prefix = (
            "https://raw.githubusercontent.com/yandex-research/StructMemEval/"
            f"{SOURCE_HEAD}/"
        )
        if not allow_other_url and not source.startswith(expected_prefix):
            fail(
                "URL must be pinned to yandex-research/StructMemEval "
                f"{SOURCE_HEAD}; use --allow-other-url for review-only overrides"
            )
        with urllib.request.urlopen(source, timeout=30) as response:
            return response.read(), "url"
    path = Path(source)
    if not path.is_file():
        fail(f"case file not found: {source}")
    return path.read_bytes(), "file"


def require_obj(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{path} must be an object")
    return value


def require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        fail(f"{path} must be an array")
    return value


def require_str(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{path} must be a non-empty string")
    return value


def sanitize_key_part(value: str) -> str:
    out = re.sub(r"[^a-zA-Z0-9_.:-]+", "_", value.strip())
    return out.strip("_") or "unknown"


def reference_shape(value: Any) -> str:
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if value is None:
        return "null"
    return type(value).__name__


def validate_case(family: str, raw: bytes, source: str, source_mode: str) -> dict[str, Any]:
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - report exact parse failure to operator
        fail(f"failed to parse {source}: {exc}")

    obj = require_obj(data, "case")
    case_id = sanitize_key_part(require_str(obj.get("case_id"), "case.case_id"))
    sessions = require_list(obj.get("sessions"), "case.sessions")
    queries = require_list(obj.get("queries"), "case.queries")
    if not sessions:
        fail(f"{source}: case.sessions must not be empty")
    if not queries:
        fail(f"{source}: case.queries must not be empty")

    records: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    session_count = 0
    turn_count = 0
    query_count = 0
    reference_shapes: dict[str, int] = {}

    for session_index, session_raw in enumerate(sessions, start=1):
        session = require_obj(session_raw, f"sessions[{session_index - 1}]")
        session_id = sanitize_key_part(
            str(session.get("session_id") or f"session_{session_index:02d}")
        )
        messages = require_list(session.get("messages"), f"sessions[{session_index - 1}].messages")
        if not messages:
            fail(f"{source}: session {session_id} has no messages")
        session_key = f"structmemeval:{family}:{case_id}:session:{session_id}"
        records.append(
            {
                "key": session_key,
                "kind": "benchmark_synthetic_session",
                "tags": ["structmemeval", "synthetic", "no_write", f"family:{family}"],
                "scope": "benchmark:structmemeval",
            }
        )
        session_count += 1

        for turn_index, msg_raw in enumerate(messages, start=1):
            msg = require_obj(msg_raw, f"sessions[{session_index - 1}].messages[{turn_index - 1}]")
            role = require_str(msg.get("role"), f"message.role")
            if role not in {"user", "assistant", "system"}:
                fail(f"{source}: unsupported role {role!r}")
            require_str(msg.get("content"), "message.content")
            turn_key = (
                f"structmemeval:{family}:{case_id}:session:{session_id}:"
                f"turn:{turn_index:04d}"
            )
            records.append(
                {
                    "key": turn_key,
                    "kind": "benchmark_synthetic_event",
                    "tags": [
                        "structmemeval",
                        "synthetic",
                        "no_write",
                        f"family:{family}",
                        f"role:{role}",
                    ],
                    "scope": "benchmark:structmemeval",
                }
            )
            edges.append(
                {
                    "from_key": session_key,
                    "to_key": turn_key,
                    "edge_type": "derived_from",
                    "weight": 1.0,
                }
            )
            turn_count += 1

    for query_index, query_raw in enumerate(queries, start=1):
        query = require_obj(query_raw, f"queries[{query_index - 1}]")
        query_id = sanitize_key_part(str(query.get("query_id") or f"q{query_index:02d}"))
        require_str(query.get("question"), f"queries[{query_index - 1}].question")
        shape = reference_shape(query.get("reference_answer"))
        reference_shapes[shape] = reference_shapes.get(shape, 0) + 1
        query_key = f"structmemeval:{family}:{case_id}:query:{query_id}"
        records.append(
            {
                "key": query_key,
                "kind": "benchmark_synthetic_query",
                "tags": ["structmemeval", "synthetic", "no_write", f"family:{family}"],
                "scope": "benchmark:structmemeval",
            }
        )
        for session_raw in sessions:
            session_id = sanitize_key_part(str(session_raw.get("session_id") or "session_01"))
            edges.append(
                {
                    "from_key": query_key,
                    "to_key": f"structmemeval:{family}:{case_id}:session:{session_id}",
                    "edge_type": "relates",
                    "weight": 1.0,
                }
            )
        query_count += 1

    keys = [record["key"] for record in records]
    if len(keys) != len(set(keys)):
        fail(f"{source}: projection generated duplicate keys")

    return {
        "family": family,
        "case_id": case_id,
        "source": source,
        "source_mode": source_mode,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "session_count": session_count,
        "turn_count": turn_count,
        "query_count": query_count,
        "reference_answer_shapes": dict(sorted(reference_shapes.items())),
        "temporary_record_count": len(records),
        "temporary_edge_count": len(edges),
        "sample_record_keys": keys[:8],
        "sample_edge_types": sorted({edge["edge_type"] for edge in edges}),
    }


def table_count(con: sqlite3.Connection, table: str) -> int | None:
    exists = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    if not exists:
        return None
    return int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def store_counts(db_path: str) -> dict[str, int | None]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return {table: table_count(con, table) for table in COUNT_TABLES}
    finally:
        con.close()


def no_write_packet(db_path: str | None, before: dict[str, int | None] | None) -> dict[str, Any]:
    if not db_path or before is None:
        return {
            "checked": False,
            "reason": "store_db_not_provided",
            "memory_rows_delta": None,
            "memory_edges_delta": None,
            "semantic_events_delta": None,
        }
    after = store_counts(db_path)
    deltas: dict[str, int | None] = {}
    for table in COUNT_TABLES:
        if before[table] is None or after[table] is None:
            deltas[table] = None
        else:
            deltas[table] = after[table] - before[table]
    return {
        "checked": True,
        "store_db": db_path,
        "before": before,
        "after": after,
        "memory_rows_delta": deltas["memories"],
        "memory_edges_delta": deltas["memory_edges"],
        "semantic_events_delta": deltas["semantic_events"],
        "passed": all(deltas[table] == 0 for table in COUNT_TABLES),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        metavar="FAMILY=PATH_OR_URL",
        help="StructMemEval case source. Repeatable. Defaults to three pinned URLs.",
    )
    parser.add_argument("--output", help="Write JSON packet to this path.")
    parser.add_argument("--store-db", help="Optional SQLite DB for no-write row-count proof.")
    parser.add_argument(
        "--allow-other-url",
        action="store_true",
        help="Review-only override for non-default URLs. Verification should not use this.",
    )
    args = parser.parse_args()

    case_specs = [parse_case_arg(raw) for raw in args.case] if args.case else DEFAULT_CASES
    before = store_counts(args.store_db) if args.store_db else None

    cases = []
    for family, source in case_specs:
        raw, source_mode = load_source(source, args.allow_other_url)
        cases.append(validate_case(family, raw, source, source_mode))

    summary = {
        "input_case_count": len(cases),
        "session_count": sum(case["session_count"] for case in cases),
        "turn_count": sum(case["turn_count"] for case in cases),
        "query_count": sum(case["query_count"] for case in cases),
        "temporary_record_count": sum(case["temporary_record_count"] for case in cases),
        "temporary_edge_count": sum(case["temporary_edge_count"] for case in cases),
        "reference_answer_shapes": {},
    }
    for case in cases:
        for shape, count in case["reference_answer_shapes"].items():
            summary["reference_answer_shapes"][shape] = (
                summary["reference_answer_shapes"].get(shape, 0) + count
            )
    summary["reference_answer_shapes"] = dict(sorted(summary["reference_answer_shapes"].items()))

    packet = {
        "schema": SCHEMA,
        "source_head": SOURCE_HEAD,
        "official_runner_import_allowed": False,
        "third_party_runtime_dependencies": False,
        "api_key_required": False,
        "private_memory_export_allowed": False,
        "writes_ab_store": False,
        "raw_content_in_output": False,
        "projection_kind_set": [
            "benchmark_synthetic_session",
            "benchmark_synthetic_event",
            "benchmark_synthetic_query",
        ],
        "summary": summary,
        "cases": cases,
        "no_write_invariant": no_write_packet(args.store_db, before),
    }

    if packet["no_write_invariant"].get("checked") and not packet["no_write_invariant"].get("passed"):
        if args.output:
            Path(args.output).write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n")
        fail("no-write invariant failed")

    text = json.dumps(packet, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
