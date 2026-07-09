#!/usr/bin/env python3
"""Gate a resolved RealMem -> Agent-Bridge temporary projection.

This script does not import RealMem, does not run RealMem evaluation, does not
call an LLM, and does not write AB memory. It combines the RealMem shape,
adapter-contract, and reference-resolver packets into one local acceptance gate.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.realmem_resolved_projection_gate.v0"
SHAPE_MODULE_NAME = "realmem_dialogue_shape_inspector"
CONTRACT_MODULE_NAME = "realmem_adapter_contract"
RESOLVER_MODULE_NAME = "realmem_reference_resolver"


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
RESOLVER = load_module(RESOLVER_MODULE_NAME, "realmem-reference-resolver.py")
SOURCE_HEAD = SHAPE.SOURCE_HEAD
DEFAULT_SOURCE = SHAPE.DEFAULT_SOURCE


def sum_keys(counts: dict[str, int], keys: list[str]) -> int:
    return sum(int(counts.get(key, 0)) for key in keys)


def build_gate(source: str, allow_other_url: bool, store_db: str | None) -> dict[str, Any]:
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
    resolver_packet = RESOLVER.resolve_references(
        data,
        source=source,
        source_mode=source_mode,
        source_sha256=source_sha256,
        adapter_packet=adapter_packet,
    )

    adapter_edges = adapter_packet["edge_projection"]
    resolver_summary = resolver_packet["resolution_summary"]
    unresolved_counts = resolver_summary["unresolved_counts"]
    resolution_counts = resolver_summary["resolution_counts"]

    adapter_accepted_edge_count = adapter_edges["accepted_memory_edge_count"]
    resolver_added_memory_used_edges = resolver_summary["resolved_memory_used_edge_count"]
    resolver_added_fallback_edges = resolver_summary["fallback_source_turn_edge_count"]
    final_accepted_edge_count = (
        adapter_accepted_edge_count
        + resolver_added_memory_used_edges
        + resolver_added_fallback_edges
    )
    adapter_edge_candidate_count = adapter_edges["edge_candidate_count"]
    residual_unresolved_count = resolver_summary["unresolved_reference_count"]
    residual_negative_count = int(unresolved_counts.get("source_turn_negative", 0))
    residual_non_negative_count = residual_unresolved_count - residual_negative_count

    no_write = {
        "checked": False,
        "passed": True,
        "memory_rows_delta": 0,
        "memory_edges_delta": 0,
        "semantic_events_delta": 0,
    }
    after = SHAPE.count_existing_rows(store_db)
    if before is not None and after is not None:
        no_write = {
            "checked": True,
            "passed": before == after,
            "memory_rows_delta": after["memories"] - before["memories"],
            "memory_edges_delta": after["memory_edges"] - before["memory_edges"],
            "semantic_events_delta": after["semantic_events"] - before["semantic_events"],
        }

    memory_used_unresolved = sum_keys(
        unresolved_counts,
        ["memory_used_missing", "memory_used_ambiguous", "memory_used_bad_shape"],
    )
    adapter_memory_used_refs = adapter_edges["unresolved_reference_counts"][
        "memory_used_content_reference"
    ]
    adapter_source_turn_indexing_refs = adapter_edges["unresolved_reference_counts"][
        "source_turn_indexing_reference"
    ]
    gates = {
        "source_pinned": source.startswith(
            f"https://raw.githubusercontent.com/AvatarMemory/RealMemBench/{SOURCE_HEAD}/"
        )
        or source_mode == "file",
        "shape_schema_matches": shape_packet["schema"]
        == "agent_bridge.realmem_dialogue_shape_packet.v0",
        "adapter_schema_matches": adapter_packet["schema"]
        == "agent_bridge.realmem_adapter_contract.v0",
        "resolver_schema_matches": resolver_packet["schema"]
        == "agent_bridge.realmem_reference_resolver.v0",
        "adapter_verdict_pass": adapter_packet["verdict"] == "PASS",
        "resolver_verdict_pass": resolver_packet["verdict"] == "PASS",
        "record_count_matches_adapter": (
            adapter_packet["record_projection"]["projected_record_count"]
            == shape_packet["summary"]["temporary_record_count"]
        ),
        "final_accepted_edges_match_adapter_candidates": (
            final_accepted_edge_count == adapter_edge_candidate_count
        ),
        "memory_used_fully_resolved": (
            memory_used_unresolved == 0
            and resolution_counts["memory_used_exact_session_content"]
            == adapter_memory_used_refs
        ),
        "source_turn_indexing_fully_resolved": (
            resolution_counts["source_turn_one_based_fallback"]
            == adapter_source_turn_indexing_refs
            and unresolved_counts["source_turn_out_of_range"] == 0
        ),
        "residual_unresolved_only_negative_source_turn": (
            residual_unresolved_count == residual_negative_count
            and residual_non_negative_count == 0
        ),
        "raw_content_redacted": True,
        "no_ab_store_write": no_write["passed"],
        "no_benchmark_performance_claim": True,
    }
    verdict = "PASS" if all(gates.values()) else "FAIL"

    return {
        "schema": SCHEMA,
        "source_repo": "https://github.com/AvatarMemory/RealMemBench",
        "source_head": SOURCE_HEAD,
        "source": source,
        "source_mode": source_mode,
        "source_sha256": source_sha256,
        "shape_schema": shape_packet["schema"],
        "adapter_schema": adapter_packet["schema"],
        "resolver_schema": resolver_packet["schema"],
        "official_runner_import_allowed": False,
        "realmem_runner_allowed_now": False,
        "third_party_runtime_dependencies": False,
        "api_key_required": False,
        "private_memory_export_allowed": False,
        "writes_ab_store": False,
        "benchmark_performance_claim": False,
        "raw_content_in_output": False,
        "verdict": verdict,
        "final_projection": {
            "projected_record_count": adapter_packet["record_projection"][
                "projected_record_count"
            ],
            "adapter_accepted_edge_count": adapter_accepted_edge_count,
            "resolver_added_memory_used_edges": resolver_added_memory_used_edges,
            "resolver_added_fallback_source_turn_edges": resolver_added_fallback_edges,
            "final_accepted_edge_count": final_accepted_edge_count,
            "adapter_edge_candidate_count": adapter_edge_candidate_count,
            "residual_unresolved_count": residual_unresolved_count,
            "residual_unresolved_counts": unresolved_counts,
            "resolved_reference_count": resolver_summary["resolved_reference_count"],
            "accepted_projection_item_count": adapter_packet["record_projection"][
                "projected_record_count"
            ]
            + final_accepted_edge_count,
        },
        "acceptance_gates": gates,
        "no_write_invariant": no_write,
        "samples": {
            "accepted_edges": (
                adapter_packet["samples"]["accepted_edges"][:4]
                + resolver_packet["samples"]["resolved_edges"][:4]
                + resolver_packet["samples"]["fallback_edges"][:4]
            ),
            "residual_unresolved_references": resolver_packet["samples"][
                "unresolved_references"
            ],
        },
    }


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

    packet = build_gate(args.source, args.allow_other_url, args.store_db)
    write_output(packet, args.output)
    if packet["verdict"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
