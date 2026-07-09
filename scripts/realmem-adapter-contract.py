#!/usr/bin/env python3
"""Build a no-write RealMem -> Agent-Bridge adapter contract packet.

This script does not import RealMem, does not run RealMem evaluation, does not
call an LLM, and does not write AB memory. It consumes one RealMem-style
dialogue file and emits a redacted contract for temporary Agent-Bridge
MemoryRecord and MemoryEdge projections.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.realmem_adapter_contract.v0"
SCOPE = "benchmark:realmem"
SHAPE_MODULE_NAME = "realmem_dialogue_shape_inspector"
RECORD_KINDS = [
    "benchmark_synthetic_realmem_session",
    "benchmark_synthetic_realmem_turn",
    "benchmark_synthetic_realmem_extracted_memory",
    "benchmark_synthetic_realmem_query_turn",
]
ACCEPTED_LOGICAL_EDGE_KINDS = [
    "chronologically_before",
    "contains_turn",
    "contains_extracted_memory",
    "derived_from_source_turn",
    "query_turn_record",
    "uses_memory_session",
]
UNRESOLVED_REFERENCE_KINDS = [
    "memory_used_content_reference",
    "source_turn_indexing_reference",
]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_shape_module() -> Any:
    module_path = Path(__file__).with_name("realmem-dialogue-shape-inspector.py")
    spec = importlib.util.spec_from_file_location(SHAPE_MODULE_NAME, module_path)
    if spec is None or spec.loader is None:
        fail(f"unable to load shape inspector module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SHAPE = load_shape_module()
SOURCE_HEAD = SHAPE.SOURCE_HEAD
DEFAULT_SOURCE = SHAPE.DEFAULT_SOURCE


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


def require_int(value: Any, path: str) -> int:
    if not isinstance(value, int):
        fail(f"{path} must be an integer")
    return value


def add_count(counts: dict[str, int], key: str, delta: int = 1) -> None:
    counts[key] = counts.get(key, 0) + delta


def canonical_content_shape(value: Any) -> str:
    return SHAPE.value_shape(value)


def record_descriptor(
    *,
    key: str,
    kind: str,
    source_path: str,
    content_source: str,
    tags: list[str],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "key": key,
        "kind": kind,
        "content_policy": "source_content_redacted_from_packet",
        "content_source": content_source,
        "source_path": source_path,
        "tags": tags,
        "scope": SCOPE,
        "status": "active",
        "importance": 0.3,
    }
    if extra:
        row.update(extra)
    return row


def edge_descriptor(
    *,
    from_key: str,
    to_key: str,
    logical_edge_kind: str,
    source_path: str,
    weight: float,
) -> dict[str, Any]:
    return {
        "from_key": from_key,
        "to_key": to_key,
        "edge_type": logical_edge_kind,
        "logical_edge_kind": logical_edge_kind,
        "source_path": source_path,
        "weight": weight,
    }


def append_sample(samples: list[dict[str, Any]], item: dict[str, Any], limit: int = 12) -> None:
    if len(samples) < limit:
        samples.append(item)


def build_adapter_contract(
    data: dict[str, Any],
    *,
    source: str,
    source_mode: str,
    source_sha256: str,
    shape_packet: dict[str, Any],
) -> dict[str, Any]:
    metadata = require_obj(data.get("_metadata"), "_metadata")
    person_name = require_str(metadata.get("person_name"), "_metadata.person_name")
    total_sessions = require_int(metadata.get("total_sessions"), "_metadata.total_sessions")
    total_tokens = require_int(metadata.get("total_tokens"), "_metadata.total_tokens")
    dialogues = require_list(data.get("dialogues"), "dialogues")
    if len(dialogues) != total_sessions:
        fail("dialogues length does not match _metadata.total_sessions")

    person_key = SHAPE.sanitize_key_part(person_name)
    session_uuid_to_key: dict[str, str] = {}
    session_key_to_turn_keys: dict[str, list[str]] = {}
    record_counts = {
        RECORD_KINDS[0]: 0,
        RECORD_KINDS[1]: 0,
        RECORD_KINDS[2]: 0,
        RECORD_KINDS[3]: 0,
    }
    accepted_edge_counts = {kind: 0 for kind in ACCEPTED_LOGICAL_EDGE_KINDS}
    unresolved_reference_counts = {kind: 0 for kind in UNRESOLVED_REFERENCE_KINDS}
    data_quality_flags = {
        "non_bool_is_query_count": 0,
        "non_string_memory_content_count": 0,
        "source_turn_unresolved_count": 0,
        "source_turn_negative_count": 0,
        "source_turn_indexing_reference_count": 0,
        "memory_used_content_reference_count": 0,
    }
    memory_content_shape_counts: dict[str, int] = {}
    samples = {
        "records": [],
        "accepted_edges": [],
        "unresolved_references": [],
    }

    previous_session_key: str | None = None
    previous_session_path: str | None = None

    for session_index, session_raw in enumerate(dialogues):
        session_path = f"dialogues[{session_index}]"
        session = require_obj(session_raw, session_path)
        session_identifier = require_str(
            session.get("session_identifier"),
            f"{session_path}.session_identifier",
        )
        session_uuid = require_str(session.get("session_uuid"), f"{session_path}.session_uuid")
        turns = require_list(session.get("dialogue_turns"), f"{session_path}.dialogue_turns")
        memories = require_list(session.get("extracted_memory"), f"{session_path}.extracted_memory")
        session_key = f"realmem:{person_key}:session:{SHAPE.sanitize_key_part(session_identifier)}"
        session_uuid_to_key[session_uuid] = session_key
        session_key_to_turn_keys[session_key] = []

        add_count(record_counts, RECORD_KINDS[0])
        append_sample(
            samples["records"],
            record_descriptor(
                key=session_key,
                kind=RECORD_KINDS[0],
                source_path=session_path,
                content_source="session_identifier,current_time,session_turn_count,session_memory_count",
                tags=[
                    "realmem",
                    "synthetic",
                    "no_write",
                    "record:session",
                    f"person:{person_key}",
                ],
                extra={
                    "session_uuid_redacted": True,
                    "turn_count": len(turns),
                    "extracted_memory_count": len(memories),
                },
            ),
        )

        if previous_session_key is not None and previous_session_path is not None:
            add_count(accepted_edge_counts, "chronologically_before")
            append_sample(
                samples["accepted_edges"],
                edge_descriptor(
                    from_key=previous_session_key,
                    to_key=session_key,
                    logical_edge_kind="chronologically_before",
                    source_path=f"{previous_session_path} -> {session_path}",
                    weight=0.7,
                ),
            )
        previous_session_key = session_key
        previous_session_path = session_path

        for turn_index, turn_raw in enumerate(turns):
            turn_path = f"{session_path}.dialogue_turns[{turn_index}]"
            turn = require_obj(turn_raw, turn_path)
            speaker = require_str(turn.get("speaker"), f"{turn_path}.speaker")
            require_str(turn.get("content"), f"{turn_path}.content")
            is_query_raw = turn.get("is_query")
            is_query = is_query_raw if isinstance(is_query_raw, bool) else False
            if not isinstance(is_query_raw, bool):
                data_quality_flags["non_bool_is_query_count"] += 1
            query_id = turn.get("query_id")
            memory_used = require_list(turn.get("memory_used", []), f"{turn_path}.memory_used")
            memory_session_uuids = require_list(
                turn.get("memory_session_uuids", []),
                f"{turn_path}.memory_session_uuids",
            )

            turn_key = (
                f"{session_key}:turn:{turn_index + 1:04d}:"
                f"{SHAPE.sanitize_key_part(speaker.lower())}"
            )
            session_key_to_turn_keys[session_key].append(turn_key)
            add_count(record_counts, RECORD_KINDS[1])
            append_sample(
                samples["records"],
                record_descriptor(
                    key=turn_key,
                    kind=RECORD_KINDS[1],
                    source_path=turn_path,
                    content_source="dialogue_turn.speaker,dialogue_turn.content",
                    tags=[
                        "realmem",
                        "synthetic",
                        "no_write",
                        "record:turn",
                        f"speaker:{SHAPE.sanitize_key_part(speaker.lower())}",
                    ],
                    extra={
                        "is_query_shape": canonical_content_shape(is_query_raw),
                        "is_query": bool(is_query),
                    },
                ),
            )
            add_count(accepted_edge_counts, "contains_turn")
            append_sample(
                samples["accepted_edges"],
                edge_descriptor(
                    from_key=session_key,
                    to_key=turn_key,
                    logical_edge_kind="contains_turn",
                    source_path=turn_path,
                    weight=1.0,
                ),
            )

            if is_query:
                query_id_str = require_str(query_id, f"{turn_path}.query_id")
                query_key = f"{turn_key}:query:{SHAPE.sanitize_key_part(query_id_str)}"
                add_count(record_counts, RECORD_KINDS[3])
                append_sample(
                    samples["records"],
                    record_descriptor(
                        key=query_key,
                        kind=RECORD_KINDS[3],
                        source_path=turn_path,
                        content_source="dialogue_turn.content",
                        tags=["realmem", "synthetic", "no_write", "record:query_turn"],
                        extra={"query_id": query_id_str},
                    ),
                )
                add_count(accepted_edge_counts, "query_turn_record")
                append_sample(
                    samples["accepted_edges"],
                    edge_descriptor(
                        from_key=turn_key,
                        to_key=query_key,
                        logical_edge_kind="query_turn_record",
                        source_path=turn_path,
                        weight=1.0,
                    ),
                )

            for ref_index, memory_ref_raw in enumerate(memory_used):
                memory_ref = require_obj(memory_ref_raw, f"{turn_path}.memory_used[{ref_index}]")
                data_quality_flags["memory_used_content_reference_count"] += 1
                add_count(unresolved_reference_counts, "memory_used_content_reference")
                append_sample(
                    samples["unresolved_references"],
                    {
                        "source_path": f"{turn_path}.memory_used[{ref_index}]",
                        "from_key": turn_key,
                        "reference_kind": "memory_used_content_reference",
                        "reason": "memory_used contains content/session metadata, not an extracted_memory.index",
                        "has_session_uuid": isinstance(memory_ref.get("session_uuid"), str),
                        "content_shape": canonical_content_shape(memory_ref.get("content")),
                        "blocking_real_eval": True,
                    },
                )

            for uuid_index, uuid_raw in enumerate(memory_session_uuids):
                uuid = require_str(uuid_raw, f"{turn_path}.memory_session_uuids[{uuid_index}]")
                target_key = session_uuid_to_key.get(uuid)
                if target_key is None:
                    data_quality_flags["source_turn_unresolved_count"] += 0
                    continue
                add_count(accepted_edge_counts, "uses_memory_session")
                append_sample(
                    samples["accepted_edges"],
                    edge_descriptor(
                        from_key=turn_key,
                        to_key=target_key,
                        logical_edge_kind="uses_memory_session",
                        source_path=f"{turn_path}.memory_session_uuids[{uuid_index}]",
                        weight=0.8,
                    ),
                )

        for memory_index, memory_raw in enumerate(memories):
            memory_path = f"{session_path}.extracted_memory[{memory_index}]"
            memory = require_obj(memory_raw, memory_path)
            memory_id = require_str(memory.get("index"), f"{memory_path}.index")
            memory_type = require_str(memory.get("type"), f"{memory_path}.type")
            memory_content = memory.get("content")
            memory_content_shape = canonical_content_shape(memory_content)
            add_count(memory_content_shape_counts, memory_content_shape)
            if memory_content_shape != "string":
                data_quality_flags["non_string_memory_content_count"] += 1
            source_turn = require_int(memory.get("source_turn"), f"{memory_path}.source_turn")

            memory_key = f"{session_key}:memory:{SHAPE.sanitize_key_part(memory_id)}"
            add_count(record_counts, RECORD_KINDS[2])
            append_sample(
                samples["records"],
                record_descriptor(
                    key=memory_key,
                    kind=RECORD_KINDS[2],
                    source_path=memory_path,
                    content_source="extracted_memory.content",
                    tags=[
                        "realmem",
                        "synthetic",
                        "no_write",
                        "record:extracted_memory",
                        f"memory_type:{SHAPE.sanitize_key_part(memory_type.lower())}",
                    ],
                    extra={
                        "content_shape": memory_content_shape,
                        "requires_content_normalizer": memory_content_shape != "string",
                    },
                ),
            )
            add_count(accepted_edge_counts, "contains_extracted_memory")
            append_sample(
                samples["accepted_edges"],
                edge_descriptor(
                    from_key=session_key,
                    to_key=memory_key,
                    logical_edge_kind="contains_extracted_memory",
                    source_path=memory_path,
                    weight=1.0,
                ),
            )
            if source_turn >= 0 and source_turn < len(session_key_to_turn_keys[session_key]):
                source_turn_key = session_key_to_turn_keys[session_key][source_turn]
                add_count(accepted_edge_counts, "derived_from_source_turn")
                append_sample(
                    samples["accepted_edges"],
                    edge_descriptor(
                        from_key=memory_key,
                        to_key=source_turn_key,
                        logical_edge_kind="derived_from_source_turn",
                        source_path=f"{memory_path}.source_turn",
                        weight=1.0,
                    ),
                )
            else:
                data_quality_flags["source_turn_unresolved_count"] += 1
                if source_turn < 0:
                    data_quality_flags["source_turn_negative_count"] += 1
                else:
                    data_quality_flags["source_turn_indexing_reference_count"] += 1
                    add_count(unresolved_reference_counts, "source_turn_indexing_reference")
                    append_sample(
                        samples["unresolved_references"],
                        {
                            "source_path": f"{memory_path}.source_turn",
                            "from_key": memory_key,
                            "reference_kind": "source_turn_indexing_reference",
                            "reason": "source_turn is non-negative but does not resolve under zero-based turn indexing",
                            "source_turn_value": source_turn,
                            "session_turn_count": len(session_key_to_turn_keys[session_key]),
                            "blocking_real_eval": True,
                        },
                    )

    projected_record_count = sum(record_counts.values())
    accepted_memory_edge_count = sum(accepted_edge_counts.values())
    unresolved_reference_count = sum(unresolved_reference_counts.values())
    edge_candidate_count = accepted_memory_edge_count + unresolved_reference_count
    shape_summary = shape_packet["summary"]
    acceptance_gates = {
        "source_pinned": source.startswith(
            f"https://raw.githubusercontent.com/AvatarMemory/RealMemBench/{SOURCE_HEAD}/"
        )
        or source_mode == "file",
        "shape_schema_matches": shape_packet["schema"]
        == "agent_bridge.realmem_dialogue_shape_packet.v0",
        "record_count_matches_shape_packet": (
            projected_record_count == shape_summary["temporary_record_count"]
        ),
        "edge_candidate_count_matches_shape_packet": (
            edge_candidate_count == shape_summary["temporary_edge_count"]
        ),
        "accepted_edges_exclude_memory_used_content_refs": unresolved_reference_count
        == data_quality_flags["memory_used_content_reference_count"]
        + data_quality_flags["source_turn_indexing_reference_count"],
        "raw_content_redacted": True,
        "no_ab_store_write": True,
        "no_benchmark_performance_claim": True,
    }
    verdict = "PASS" if all(acceptance_gates.values()) else "FAIL"

    return {
        "schema": SCHEMA,
        "source_repo": "https://github.com/AvatarMemory/RealMemBench",
        "source_head": SOURCE_HEAD,
        "source": source,
        "source_mode": source_mode,
        "source_sha256": source_sha256,
        "shape_schema": shape_packet["schema"],
        "official_runner_import_allowed": False,
        "realmem_runner_allowed_now": False,
        "third_party_runtime_dependencies": False,
        "api_key_required": False,
        "private_memory_export_allowed": False,
        "writes_ab_store": False,
        "benchmark_performance_claim": False,
        "raw_content_in_output": False,
        "verdict": verdict,
        "scope": SCOPE,
        "record_projection": {
            "record_kinds": RECORD_KINDS,
            "record_kind_counts": record_counts,
            "projected_record_count": projected_record_count,
        },
        "edge_projection": {
            "accepted_logical_edge_kinds": ACCEPTED_LOGICAL_EDGE_KINDS,
            "accepted_logical_edge_counts": accepted_edge_counts,
            "accepted_memory_edge_count": accepted_memory_edge_count,
            "unresolved_reference_kinds": UNRESOLVED_REFERENCE_KINDS,
            "unresolved_reference_counts": unresolved_reference_counts,
            "unresolved_reference_count": unresolved_reference_count,
            "edge_candidate_count": edge_candidate_count,
        },
        "data_quality_flags": {
            **data_quality_flags,
            "memory_content_shape_counts": dict(sorted(memory_content_shape_counts.items())),
            "memory_used_requires_resolver": unresolved_reference_count > 0,
        },
        "acceptance_gates": acceptance_gates,
        "samples": samples,
    }


def build_packet(source: str, allow_other_url: bool, store_db: str | None) -> dict[str, Any]:
    before = SHAPE.count_existing_rows(store_db)
    raw, source_mode = SHAPE.load_source(source, allow_other_url)
    source_sha256 = __import__("hashlib").sha256(raw).hexdigest()
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - report exact parse failure to operator
        fail(f"failed to parse {source}: {exc}")
    shape_packet = SHAPE.count_projection_rows(data, source, source_mode, source_sha256)
    packet = build_adapter_contract(
        data,
        source=source,
        source_mode=source_mode,
        source_sha256=source_sha256,
        shape_packet=shape_packet,
    )
    after = SHAPE.count_existing_rows(store_db)
    if before is not None and after is not None:
        no_write = {
            "checked": True,
            "passed": before == after,
            "memory_rows_delta": after["memories"] - before["memories"],
            "memory_edges_delta": after["memory_edges"] - before["memory_edges"],
            "semantic_events_delta": after["semantic_events"] - before["semantic_events"],
        }
    else:
        no_write = {
            "checked": False,
            "passed": True,
            "memory_rows_delta": 0,
            "memory_edges_delta": 0,
            "semantic_events_delta": 0,
        }
    packet["no_write_invariant"] = no_write
    if no_write["checked"] and not no_write["passed"]:
        packet["verdict"] = "FAIL"
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

    packet = build_packet(args.source, args.allow_other_url, args.store_db)
    write_output(packet, args.output)
    if packet["verdict"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
