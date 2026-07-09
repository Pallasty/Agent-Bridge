#!/usr/bin/env python3
"""Inspect a RealMem dialogue JSON shape without running a benchmark.

This script does not import RealMem, does not run RealMem evaluation, does not
call an LLM, and does not write AB memory. It validates one RealMem-style
dialogue file, builds temporary in-memory AB-like projection counts, and emits a
redacted shape packet suitable for review reports.
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


SCHEMA = "agent_bridge.realmem_dialogue_shape_packet.v0"
SOURCE_HEAD = "67afd0891d603adcc4458ff0449df306ef296b7a"
DEFAULT_SOURCE = (
    "https://raw.githubusercontent.com/AvatarMemory/RealMemBench/"
    f"{SOURCE_HEAD}/dataset/Lin_Wanyu_dialogues_256k.json"
)
COUNT_TABLES = ["memories", "memory_edges", "semantic_events"]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_source(source: str, allow_other_url: bool) -> tuple[bytes, str]:
    if source.startswith("http://"):
        fail("http URLs are refused; use https")
    if source.startswith("https://"):
        expected_prefix = (
            "https://raw.githubusercontent.com/AvatarMemory/RealMemBench/"
            f"{SOURCE_HEAD}/"
        )
        if not allow_other_url and not source.startswith(expected_prefix):
            fail(
                "URL must be pinned to AvatarMemory/RealMemBench "
                f"{SOURCE_HEAD}; use --allow-other-url for review-only overrides"
            )
        request = urllib.request.Request(
            source, headers={"User-Agent": "agent-bridge-realmem-shape-inspector"}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read(), "url"
    path = Path(source)
    if not path.is_file():
        fail(f"dialogue file not found: {source}")
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


def require_string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        fail(f"{path} must be a string")
    return value


def require_bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        fail(f"{path} must be a boolean")
    return value


def require_int(value: Any, path: str) -> int:
    if not isinstance(value, int):
        fail(f"{path} must be an integer")
    return value


def sanitize_key_part(value: str) -> str:
    out = re.sub(r"[^a-zA-Z0-9_.:-]+", "_", value.strip())
    return out.strip("_") or "unknown"


def value_shape(value: Any) -> str:
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if value is None:
        return "null"
    return type(value).__name__


def count_existing_rows(db_path: str | None) -> dict[str, int] | None:
    if not db_path:
        return None
    path = Path(db_path)
    if not path.is_file():
        fail(f"store db not found: {db_path}")
    con = sqlite3.connect(path)
    try:
        counts: dict[str, int] = {}
        for table in COUNT_TABLES:
            row = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if row is None:
                counts[table] = 0
            else:
                counts[table] = int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return counts
    finally:
        con.close()


def count_projection_rows(
    data: dict[str, Any], source: str, source_mode: str, raw_sha256: str
) -> dict[str, Any]:
    metadata = require_obj(data.get("_metadata"), "_metadata")
    person_name = require_str(metadata.get("person_name"), "_metadata.person_name")
    total_sessions = require_int(metadata.get("total_sessions"), "_metadata.total_sessions")
    total_tokens = require_int(metadata.get("total_tokens"), "_metadata.total_tokens")
    dialogues = require_list(data.get("dialogues"), "dialogues")
    if not dialogues:
        fail("dialogues must not be empty")
    if total_sessions != len(dialogues):
        fail(
            "_metadata.total_sessions must match dialogues length "
            f"({total_sessions} != {len(dialogues)})"
        )

    person_key = sanitize_key_part(person_name)
    session_keys_seen: set[str] = set()
    session_uuid_to_key: dict[str, str] = {}
    observed_session_fields: set[str] = set()
    observed_turn_fields: set[str] = set()
    observed_memory_fields: set[str] = set()
    speaker_counts: dict[str, int] = {}
    is_query_shape_counts: dict[str, int] = {}
    memory_type_counts: dict[str, int] = {}
    memory_content_shape_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    session_type_counts: dict[str, int] = {}

    session_count = 0
    turn_count = 0
    extracted_memory_count = 0
    empty_extracted_memory_content_count = 0
    source_turn_reference_count = 0
    query_turn_count = 0
    non_bool_is_query_count = 0
    memory_used_turn_count = 0
    memory_session_uuid_turn_count = 0
    memory_used_reference_count = 0
    memory_session_uuid_reference_count = 0

    record_keys: list[str] = []
    edge_types: dict[str, int] = {
        "chronologically_before": 0,
        "contains_turn": 0,
        "contains_extracted_memory": 0,
        "derived_from_source_turn": 0,
        "query_turn_record": 0,
        "uses_memory": 0,
        "uses_memory_session": 0,
    }
    previous_session_key: str | None = None

    for session_index, session_raw in enumerate(dialogues, start=1):
        session = require_obj(session_raw, f"dialogues[{session_index - 1}]")
        observed_session_fields.update(session.keys())
        session_identifier = require_str(
            session.get("session_identifier"),
            f"dialogues[{session_index - 1}].session_identifier",
        )
        session_uuid = require_str(
            session.get("session_uuid"),
            f"dialogues[{session_index - 1}].session_uuid",
        )
        require_str(session.get("current_time"), f"dialogues[{session_index - 1}].current_time")
        turns = require_list(
            session.get("dialogue_turns"),
            f"dialogues[{session_index - 1}].dialogue_turns",
        )
        memories = require_list(
            session.get("extracted_memory"),
            f"dialogues[{session_index - 1}].extracted_memory",
        )
        if not turns:
            fail(f"session {session_identifier} has no dialogue turns")

        session_key = f"realmem:{person_key}:session:{sanitize_key_part(session_identifier)}"
        if session_key in session_keys_seen:
            fail(f"duplicate session identifier: {session_identifier}")
        session_keys_seen.add(session_key)
        session_uuid_to_key[session_uuid] = session_key
        record_keys.append(session_key)
        session_count += 1
        if previous_session_key is not None:
            edge_types["chronologically_before"] += 1
        previous_session_key = session_key

        for turn_index, turn_raw in enumerate(turns, start=1):
            turn = require_obj(
                turn_raw,
                f"dialogues[{session_index - 1}].dialogue_turns[{turn_index - 1}]",
            )
            observed_turn_fields.update(turn.keys())
            speaker = require_str(turn.get("speaker"), "dialogue_turn.speaker")
            if speaker not in {"User", "Assistant"}:
                fail(f"unsupported speaker {speaker!r}")
            require_str(turn.get("content"), "dialogue_turn.content")
            is_query_raw = turn.get("is_query")
            is_query_shape = value_shape(is_query_raw)
            is_query_shape_counts[is_query_shape] = is_query_shape_counts.get(is_query_shape, 0) + 1
            if isinstance(is_query_raw, bool):
                is_query = is_query_raw
            else:
                non_bool_is_query_count += 1
                is_query = False
            memory_used = require_list(turn.get("memory_used", []), "dialogue_turn.memory_used")
            memory_session_uuids = require_list(
                turn.get("memory_session_uuids", []),
                "dialogue_turn.memory_session_uuids",
            )
            query_id = turn.get("query_id")
            if is_query:
                require_str(query_id, "dialogue_turn.query_id")
                query_turn_count += 1

            speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1
            if isinstance(turn.get("session_type"), str) and turn["session_type"].strip():
                session_type = str(turn["session_type"])
                session_type_counts[session_type] = session_type_counts.get(session_type, 0) + 1
            if isinstance(turn.get("category_name"), str) and turn["category_name"].strip():
                category = str(turn["category_name"])
                category_counts[category] = category_counts.get(category, 0) + 1

            turn_key = (
                f"{session_key}:turn:{turn_index:04d}:{sanitize_key_part(speaker.lower())}"
            )
            record_keys.append(turn_key)
            turn_count += 1
            edge_types["contains_turn"] += 1

            if is_query:
                query_key = f"{turn_key}:query:{sanitize_key_part(str(query_id))}"
                record_keys.append(query_key)
                edge_types["query_turn_record"] += 1

            if memory_used:
                memory_used_turn_count += 1
                for memory_ref in memory_used:
                    require_obj(memory_ref, "dialogue_turn.memory_used[]")
                    memory_used_reference_count += 1
                edge_types["uses_memory"] += len(memory_used)
            if memory_session_uuids:
                memory_session_uuid_turn_count += 1
                for uuid_ref in memory_session_uuids:
                    require_str(uuid_ref, "dialogue_turn.memory_session_uuids[]")
                    memory_session_uuid_reference_count += 1
                edge_types["uses_memory_session"] += len(memory_session_uuids)

        for memory_index, memory_raw in enumerate(memories, start=1):
            memory = require_obj(
                memory_raw,
                f"dialogues[{session_index - 1}].extracted_memory[{memory_index - 1}]",
            )
            observed_memory_fields.update(memory.keys())
            memory_id = require_str(memory.get("index"), "extracted_memory.index")
            memory_type = require_str(memory.get("type"), "extracted_memory.type")
            memory_content = memory.get("content")
            memory_content_shape = value_shape(memory_content)
            memory_content_shape_counts[memory_content_shape] = (
                memory_content_shape_counts.get(memory_content_shape, 0) + 1
            )
            if isinstance(memory_content, str) and not memory_content.strip():
                empty_extracted_memory_content_count += 1
            source_turn = require_int(memory.get("source_turn"), "extracted_memory.source_turn")
            require_string(
                memory.get("source_content_snapshot"),
                "extracted_memory.source_content_snapshot",
            )
            require_string(
                memory.get("source_role_snapshot"),
                "extracted_memory.source_role_snapshot",
            )
            memory_session_uuid = require_str(
                memory.get("session_uuid"),
                "extracted_memory.session_uuid",
            )
            if memory_session_uuid not in session_uuid_to_key:
                fail(f"memory {memory_id} references unknown session_uuid")

            memory_type_counts[memory_type] = memory_type_counts.get(memory_type, 0) + 1
            memory_key = f"{session_key}:memory:{sanitize_key_part(memory_id)}"
            record_keys.append(memory_key)
            extracted_memory_count += 1
            edge_types["contains_extracted_memory"] += 1
            if source_turn >= 0:
                source_turn_reference_count += 1
                edge_types["derived_from_source_turn"] += 1

    temporary_record_count = len(record_keys)
    temporary_edge_count = sum(edge_types.values())
    raw_content_in_output = False
    no_write_summary = {
        "records_are_temporary": True,
        "edges_are_temporary": True,
        "content_fields_redacted": True,
        "memory_rows_delta": 0,
        "memory_edges_delta": 0,
        "semantic_events_delta": 0,
    }

    return {
        "schema": SCHEMA,
        "source_repo": "https://github.com/AvatarMemory/RealMemBench",
        "source_head": SOURCE_HEAD,
        "source": source,
        "source_mode": source_mode,
        "source_sha256": raw_sha256,
        "official_runner_import_allowed": False,
        "realmem_runner_allowed_now": False,
        "third_party_runtime_dependencies": False,
        "api_key_required": False,
        "private_memory_export_allowed": False,
        "writes_ab_store": False,
        "benchmark_performance_claim": False,
        "raw_content_in_output": raw_content_in_output,
        "person": {
            "person_name": person_name,
            "total_sessions": total_sessions,
            "total_tokens": total_tokens,
        },
        "summary": {
            "session_count": session_count,
            "turn_count": turn_count,
            "query_turn_count": query_turn_count,
            "non_bool_is_query_count": non_bool_is_query_count,
            "extracted_memory_count": extracted_memory_count,
            "empty_extracted_memory_content_count": empty_extracted_memory_content_count,
            "source_turn_reference_count": source_turn_reference_count,
            "memory_used_turn_count": memory_used_turn_count,
            "memory_session_uuid_turn_count": memory_session_uuid_turn_count,
            "memory_used_reference_count": memory_used_reference_count,
            "memory_session_uuid_reference_count": memory_session_uuid_reference_count,
            "temporary_record_count": temporary_record_count,
            "temporary_edge_count": temporary_edge_count,
        },
        "field_inventory": {
            "session_fields": sorted(observed_session_fields),
            "turn_fields": sorted(observed_turn_fields),
            "extracted_memory_fields": sorted(observed_memory_fields),
            "speaker_counts": dict(sorted(speaker_counts.items())),
            "is_query_shapes": dict(sorted(is_query_shape_counts.items())),
            "memory_type_counts": dict(sorted(memory_type_counts.items())),
            "extracted_memory_content_shapes": dict(
                sorted(memory_content_shape_counts.items())
            ),
            "session_type_counts": dict(sorted(session_type_counts.items())),
            "category_counts": dict(sorted(category_counts.items())),
        },
        "projection_contract": {
            "memory_record_kinds": [
                "benchmark_synthetic_persona_session",
                "benchmark_synthetic_dialogue_turn",
                "benchmark_synthetic_extracted_memory",
                "benchmark_synthetic_query_turn",
            ],
            "memory_edge_types": [k for k, v in sorted(edge_types.items()) if v > 0],
            "sample_record_keys": record_keys[:8],
            "edge_type_counts": dict(sorted(edge_types.items())),
            "no_write_summary": no_write_summary,
        },
    }


def inspect_source(source: str, allow_other_url: bool, store_db: str | None) -> dict[str, Any]:
    before = count_existing_rows(store_db)
    raw, source_mode = load_source(source, allow_other_url)
    raw_sha256 = hashlib.sha256(raw).hexdigest()
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - report parse failure to operator
        fail(f"failed to parse {source}: {exc}")
    packet = count_projection_rows(data, source, source_mode, raw_sha256)
    after = count_existing_rows(store_db)
    if before is not None and after is not None:
        proof = {
            "checked": True,
            "passed": before == after,
            "memory_rows_delta": after["memories"] - before["memories"],
            "memory_edges_delta": after["memory_edges"] - before["memory_edges"],
            "semantic_events_delta": after["semantic_events"] - before["semantic_events"],
        }
    else:
        proof = {
            "checked": False,
            "passed": True,
            "memory_rows_delta": 0,
            "memory_edges_delta": 0,
            "semantic_events_delta": 0,
        }
    packet["no_write_invariant"] = proof
    return packet


def write_output(packet: dict[str, Any], output: str | None) -> None:
    rendered = json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True)
    if output:
        Path(output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help="RealMem dialogue JSON file path or pinned raw URL.",
    )
    parser.add_argument(
        "--allow-other-url",
        action="store_true",
        help="Allow non-default HTTPS URLs for review-only source inspection.",
    )
    parser.add_argument(
        "--store-db",
        help="Optional AB SQLite store path used only to prove row counts are unchanged.",
    )
    parser.add_argument("--output", help="Optional output JSON path.")
    args = parser.parse_args(argv)

    packet = inspect_source(args.source, args.allow_other_url, args.store_db)
    write_output(packet, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
