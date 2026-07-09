#!/usr/bin/env python3
"""Resolve local RealMem reference ambiguities without running a benchmark.

This script does not import RealMem, does not run RealMem evaluation, does not
call an LLM, and does not write AB memory. It consumes one RealMem-style
dialogue file and applies deterministic local resolver rules for references
left unresolved by the adapter-contract packet.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.realmem_reference_resolver.v0"
SHAPE_MODULE_NAME = "realmem_dialogue_shape_inspector"
CONTRACT_MODULE_NAME = "realmem_adapter_contract"
RESOLUTION_KINDS = [
    "memory_used_exact_session_content",
    "source_turn_zero_based",
    "source_turn_one_based_fallback",
]
UNRESOLVED_KINDS = [
    "source_turn_negative",
    "source_turn_out_of_range",
    "memory_used_missing",
    "memory_used_ambiguous",
    "memory_used_bad_shape",
]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_module(module_name: str, file_name: str) -> Any:
    module_path = Path(__file__).with_name(file_name)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        fail(f"unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SHAPE = load_module(SHAPE_MODULE_NAME, "realmem-dialogue-shape-inspector.py")
CONTRACT = load_module(CONTRACT_MODULE_NAME, "realmem-adapter-contract.py")
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


def append_sample(samples: list[dict[str, Any]], item: dict[str, Any], limit: int = 12) -> None:
    if len(samples) < limit:
        samples.append(item)


def build_keys(data: dict[str, Any]) -> tuple[str, dict[str, str], dict[str, list[str]], dict[tuple[str, str], list[dict[str, Any]]]]:
    metadata = require_obj(data.get("_metadata"), "_metadata")
    person_name = require_str(metadata.get("person_name"), "_metadata.person_name")
    person_key = SHAPE.sanitize_key_part(person_name)
    session_uuid_to_key: dict[str, str] = {}
    session_key_to_turn_keys: dict[str, list[str]] = {}
    memory_by_session_content: dict[tuple[str, str], list[dict[str, Any]]] = {}
    dialogues = require_list(data.get("dialogues"), "dialogues")

    for session_index, session_raw in enumerate(dialogues):
        session_path = f"dialogues[{session_index}]"
        session = require_obj(session_raw, session_path)
        session_identifier = require_str(
            session.get("session_identifier"),
            f"{session_path}.session_identifier",
        )
        session_uuid = require_str(session.get("session_uuid"), f"{session_path}.session_uuid")
        session_key = f"realmem:{person_key}:session:{SHAPE.sanitize_key_part(session_identifier)}"
        session_uuid_to_key[session_uuid] = session_key
        turns = require_list(session.get("dialogue_turns"), f"{session_path}.dialogue_turns")
        memories = require_list(session.get("extracted_memory"), f"{session_path}.extracted_memory")
        turn_keys: list[str] = []
        for turn_index, turn_raw in enumerate(turns):
            turn = require_obj(turn_raw, f"{session_path}.dialogue_turns[{turn_index}]")
            speaker = require_str(turn.get("speaker"), "dialogue_turn.speaker")
            turn_keys.append(
                f"{session_key}:turn:{turn_index + 1:04d}:"
                f"{SHAPE.sanitize_key_part(speaker.lower())}"
            )
        session_key_to_turn_keys[session_key] = turn_keys
        for memory_index, memory_raw in enumerate(memories):
            memory = require_obj(memory_raw, f"{session_path}.extracted_memory[{memory_index}]")
            memory_id = require_str(memory.get("index"), "extracted_memory.index")
            memory_uuid = require_str(memory.get("session_uuid"), "extracted_memory.session_uuid")
            memory_key = f"{session_key}:memory:{SHAPE.sanitize_key_part(memory_id)}"
            content = memory.get("content")
            if isinstance(content, str):
                memory_by_session_content.setdefault((memory_uuid, content), []).append(
                    {
                        "key": memory_key,
                        "source_path": f"{session_path}.extracted_memory[{memory_index}]",
                        "session_key": session_key,
                    }
                )
    return person_key, session_uuid_to_key, session_key_to_turn_keys, memory_by_session_content


def resolve_references(
    data: dict[str, Any],
    *,
    source: str,
    source_mode: str,
    source_sha256: str,
    adapter_packet: dict[str, Any],
) -> dict[str, Any]:
    (
        _person_key,
        session_uuid_to_key,
        session_key_to_turn_keys,
        memory_by_session_content,
    ) = build_keys(data)
    dialogues = require_list(data.get("dialogues"), "dialogues")
    resolution_counts = {kind: 0 for kind in RESOLUTION_KINDS}
    unresolved_counts = {kind: 0 for kind in UNRESOLVED_KINDS}
    samples = {"resolved_edges": [], "fallback_edges": [], "unresolved_references": []}
    resolved_memory_used_edge_count = 0
    resolved_source_turn_edge_count = 0
    fallback_source_turn_edge_count = 0

    for session_index, session_raw in enumerate(dialogues):
        session_path = f"dialogues[{session_index}]"
        session = require_obj(session_raw, session_path)
        session_identifier = require_str(
            session.get("session_identifier"),
            f"{session_path}.session_identifier",
        )
        session_uuid = require_str(session.get("session_uuid"), f"{session_path}.session_uuid")
        session_key = session_uuid_to_key[session_uuid]
        turns = require_list(session.get("dialogue_turns"), f"{session_path}.dialogue_turns")
        memories = require_list(session.get("extracted_memory"), f"{session_path}.extracted_memory")

        for turn_index, turn_raw in enumerate(turns):
            turn_path = f"{session_path}.dialogue_turns[{turn_index}]"
            turn = require_obj(turn_raw, turn_path)
            speaker = require_str(turn.get("speaker"), f"{turn_path}.speaker")
            turn_key = (
                f"{session_key}:turn:{turn_index + 1:04d}:"
                f"{SHAPE.sanitize_key_part(speaker.lower())}"
            )
            memory_used = require_list(turn.get("memory_used", []), f"{turn_path}.memory_used")
            for ref_index, ref_raw in enumerate(memory_used):
                ref_path = f"{turn_path}.memory_used[{ref_index}]"
                ref = require_obj(ref_raw, ref_path)
                ref_uuid = ref.get("session_uuid")
                ref_content = ref.get("content")
                if not isinstance(ref_uuid, str) or not isinstance(ref_content, str):
                    add_count(unresolved_counts, "memory_used_bad_shape")
                    append_sample(
                        samples["unresolved_references"],
                        {
                            "source_path": ref_path,
                            "reference_kind": "memory_used_bad_shape",
                            "from_key": turn_key,
                        },
                    )
                    continue
                matches = memory_by_session_content.get((ref_uuid, ref_content), [])
                if len(matches) == 1:
                    add_count(resolution_counts, "memory_used_exact_session_content")
                    resolved_memory_used_edge_count += 1
                    append_sample(
                        samples["resolved_edges"],
                        {
                            "from_key": turn_key,
                            "to_key": matches[0]["key"],
                            "edge_type": "uses_memory",
                            "resolution_kind": "memory_used_exact_session_content",
                            "source_path": ref_path,
                            "weight": 0.9,
                        },
                    )
                elif len(matches) == 0:
                    add_count(unresolved_counts, "memory_used_missing")
                    append_sample(
                        samples["unresolved_references"],
                        {
                            "source_path": ref_path,
                            "reference_kind": "memory_used_missing",
                            "from_key": turn_key,
                            "session_uuid_present": ref_uuid in session_uuid_to_key,
                        },
                    )
                else:
                    add_count(unresolved_counts, "memory_used_ambiguous")
                    append_sample(
                        samples["unresolved_references"],
                        {
                            "source_path": ref_path,
                            "reference_kind": "memory_used_ambiguous",
                            "from_key": turn_key,
                            "candidate_count": len(matches),
                        },
                    )

        for memory_index, memory_raw in enumerate(memories):
            memory_path = f"{session_path}.extracted_memory[{memory_index}]"
            memory = require_obj(memory_raw, memory_path)
            memory_id = require_str(memory.get("index"), f"{memory_path}.index")
            source_turn = require_int(memory.get("source_turn"), f"{memory_path}.source_turn")
            memory_key = f"{session_key}:memory:{SHAPE.sanitize_key_part(memory_id)}"
            turn_keys = session_key_to_turn_keys[session_key]
            if 0 <= source_turn < len(turn_keys):
                add_count(resolution_counts, "source_turn_zero_based")
                resolved_source_turn_edge_count += 1
                append_sample(
                    samples["resolved_edges"],
                    {
                        "from_key": memory_key,
                        "to_key": turn_keys[source_turn],
                        "edge_type": "derived_from_source_turn",
                        "resolution_kind": "source_turn_zero_based",
                        "source_path": f"{memory_path}.source_turn",
                        "weight": 1.0,
                    },
                )
            elif 1 <= source_turn <= len(turn_keys):
                add_count(resolution_counts, "source_turn_one_based_fallback")
                fallback_source_turn_edge_count += 1
                append_sample(
                    samples["fallback_edges"],
                    {
                        "from_key": memory_key,
                        "to_key": turn_keys[source_turn - 1],
                        "edge_type": "derived_from_source_turn",
                        "resolution_kind": "source_turn_one_based_fallback",
                        "source_path": f"{memory_path}.source_turn",
                        "source_turn_value": source_turn,
                        "weight": 0.6,
                        "review_recommended": True,
                    },
                )
            elif source_turn < 0:
                add_count(unresolved_counts, "source_turn_negative")
                append_sample(
                    samples["unresolved_references"],
                    {
                        "from_key": memory_key,
                        "reference_kind": "source_turn_negative",
                        "source_path": f"{memory_path}.source_turn",
                        "source_turn_value": source_turn,
                    },
                )
            else:
                add_count(unresolved_counts, "source_turn_out_of_range")
                append_sample(
                    samples["unresolved_references"],
                    {
                        "from_key": memory_key,
                        "reference_kind": "source_turn_out_of_range",
                        "source_path": f"{memory_path}.source_turn",
                        "source_turn_value": source_turn,
                        "session_turn_count": len(turn_keys),
                    },
                )

    resolved_reference_count = sum(resolution_counts.values())
    unresolved_reference_count = sum(unresolved_counts.values())
    adapter_unresolved = adapter_packet["edge_projection"]["unresolved_reference_count"]
    adapter_memory_used = adapter_packet["edge_projection"]["unresolved_reference_counts"][
        "memory_used_content_reference"
    ]
    adapter_source_turn_indexing = adapter_packet["edge_projection"]["unresolved_reference_counts"][
        "source_turn_indexing_reference"
    ]
    adapter_negative = adapter_packet["data_quality_flags"]["source_turn_negative_count"]
    gates = {
        "source_pinned": source.startswith(
            f"https://raw.githubusercontent.com/AvatarMemory/RealMemBench/{SOURCE_HEAD}/"
        )
        or source_mode == "file",
        "adapter_schema_matches": adapter_packet["schema"]
        == "agent_bridge.realmem_adapter_contract.v0",
        "memory_used_resolution_count_matches_adapter": (
            resolution_counts["memory_used_exact_session_content"] == adapter_memory_used
        ),
        "source_turn_fallback_count_matches_adapter": (
            resolution_counts["source_turn_one_based_fallback"] == adapter_source_turn_indexing
        ),
        "source_turn_negative_count_matches_adapter": (
            unresolved_counts["source_turn_negative"] == adapter_negative
        ),
        "resolved_plus_unresolved_matches_adapter": (
            resolution_counts["memory_used_exact_session_content"]
            + resolution_counts["source_turn_one_based_fallback"]
            + unresolved_counts["source_turn_negative"]
            == adapter_unresolved + adapter_negative
        ),
        "raw_content_redacted": True,
        "no_ab_store_write": True,
        "no_benchmark_performance_claim": True,
    }
    return {
        "schema": SCHEMA,
        "source_repo": "https://github.com/AvatarMemory/RealMemBench",
        "source_head": SOURCE_HEAD,
        "source": source,
        "source_mode": source_mode,
        "source_sha256": source_sha256,
        "adapter_schema": adapter_packet["schema"],
        "official_runner_import_allowed": False,
        "realmem_runner_allowed_now": False,
        "third_party_runtime_dependencies": False,
        "api_key_required": False,
        "private_memory_export_allowed": False,
        "writes_ab_store": False,
        "benchmark_performance_claim": False,
        "raw_content_in_output": False,
        "verdict": "PASS" if all(gates.values()) else "FAIL",
        "resolution_rules": {
            "memory_used": "session_uuid + exact string content -> exactly one extracted_memory",
            "source_turn": "zero_based first; one_based fallback if zero_based is out of range and 1 <= source_turn <= turn_count; negative remains unresolved",
        },
        "resolution_summary": {
            "resolved_reference_count": resolved_reference_count,
            "unresolved_reference_count": unresolved_reference_count,
            "resolved_memory_used_edge_count": resolved_memory_used_edge_count,
            "resolved_source_turn_edge_count": resolved_source_turn_edge_count,
            "fallback_source_turn_edge_count": fallback_source_turn_edge_count,
            "resolution_counts": resolution_counts,
            "unresolved_counts": unresolved_counts,
        },
        "acceptance_gates": gates,
        "samples": samples,
    }


def build_packet(source: str, allow_other_url: bool, store_db: str | None) -> dict[str, Any]:
    before = SHAPE.count_existing_rows(store_db)
    raw, source_mode = SHAPE.load_source(source, allow_other_url)
    source_sha256 = __import__("hashlib").sha256(raw).hexdigest()
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        fail(f"failed to parse {source}: {exc}")
    shape_packet = SHAPE.count_projection_rows(data, source, source_mode, source_sha256)
    adapter_packet = CONTRACT.build_adapter_contract(
        data,
        source=source,
        source_mode=source_mode,
        source_sha256=source_sha256,
        shape_packet=shape_packet,
    )
    packet = resolve_references(
        data,
        source=source,
        source_mode=source_mode,
        source_sha256=source_sha256,
        adapter_packet=adapter_packet,
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
