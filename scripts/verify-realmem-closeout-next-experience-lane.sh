#!/usr/bin/env bash
# Offline verification for the RealMem closeout / next Experience lane packet.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPORT="$ROOT_DIR/docs/reports/goal-c-u/2026-07-09-realmem-closeout-next-experience-lane.md"

python3 - "$REPORT" <<'PY'
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
text = report_path.read_text(encoding="utf-8")

required = [
    "# RealMem Closeout and Next Experience Lane",
    "Source base commit: `5a4818a4`",
    "Run type: docs-only closeout and next-lane selection, no runner",
    "memory_evolution_stage: reflection",
    "experience_candidate_surface: next_lane_selection_only",
    "runtime_authority: none",
    "promotion_allowed: false",
    "private_memory_export_allowed: false",
    "third_party_runtime_dependencies: false",
    "no_write_invariant: true",
    "realmem_closeout_next_experience_lane_20260709",
    "codex-realmem-closeout-next-experience-lane-20260709_active",
    "Forum thread: `design#119`, post `2989`",
    "realmem_resolved_projection_gate_20260709",
    "realmem_local_adapter_chain_status: closed_local_gate",
    "realmem_real_runner_gate: owner_gated_boundary_packet_only",
    "selected_next_lane: memoryarena_task_shape_packet",
    "fallback_next_lane: ama_bench_interface_shape_packet",
    "selected_next_lane_stage: experience_candidate",
    "benchmark_performance_claim_allowed: false",
    "official_runner_import_allowed_now: false",
    "dependency_install_allowed_now: false",
    "private_memory_export_allowed: false",
    "writes_ab_store: false",
    "projected_record_count: 2060",
    "adapter_accepted_edge_count: 2703",
    "resolver_added_memory_used_edges: 327",
    "resolver_added_fallback_source_turn_edges: 30",
    "final_accepted_edge_count: 3060",
    "accepted_projection_item_count: 5120",
    "residual_unresolved_count: 7",
    "residual_unresolved_allowed_reason: source_turn_negative_only",
    "realmem_real_runner_boundary_packet",
    "MemoryArena",
    "ZexueHe/memoryarena",
    "sha=da1a37c8b19280e18627ca01cf368195a5e1d92e",
    "lastModified=2026-03-03T00:39:50.000Z",
    "downloads=15828",
    "likes=14",
    "701 rows",
    "12.3 MB",
    "CC-BY-4.0",
    "bundled_shopping/data.jsonl",
    "formal_reasoning_math/data.jsonl",
    "formal_reasoning_phys/data.jsonl",
    "group_travel_planner/data.jsonl",
    "progressive_search/data.jsonl",
    "question_count: 6",
    "question_count: 9",
    "question_count: 8",
    "question_count: 5",
    "question_count: 3",
    "background_type: list",
    "AMA-Bench",
    "AMA-Bench/AMA-Bench",
    "ddfd319e0be33424288c13806f1eafc63e625b59",
    "raw license is MIT",
    "scripts/evaluate.sh",
    "src/evaluate.py",
    "AMA-bench/AMA-bench",
    "sha=a5777378066f53229a94557a7b192435cd027909",
    "lastModified=2026-06-08T05:40:25.000Z",
    "test/open_end_qa_set.jsonl",
    "sample_domain: Game",
    "has_trajectory_like_key: true",
    "qa_pairs",
    "trajectory",
    "LLM-as-judge",
    "no dependency installation",
    "no MemoryArena runner or environment harness",
    "no API-key-backed generation or judging",
    "no private AB memory export",
    "no AB store writes",
    "no benchmark score or performance claim",
]

missing = [needle for needle in required if needle not in text]
if missing:
    raise SystemExit("Missing required closeout anchors: " + ", ".join(missing))

for forbidden in [
    "benchmark score is ready",
    "benchmark performance is proven",
    "MemoryArena evaluation passed",
    "AMA-Bench evaluation passed",
    "RealMem evaluation passed",
    "installed dependencies",
    "writes_ab_store: true",
    "private_memory_export_allowed: true",
    "official_runner_import_allowed_now: true",
    "dependency_install_allowed_now: true",
    "benchmark_performance_claim_allowed: true",
]:
    assert forbidden not in text

decision_index = text.index("## Decision")
snapshot_index = text.index("## Source Snapshot")
memoryarena_index = text.index("### MemoryArena Shape Notes")
ama_index = text.index("### AMA-Bench Shape Notes")
next_packet_index = text.index("## Next Work Packet")
boundary_index = text.index("## Boundary")
assert decision_index < snapshot_index < memoryarena_index < ama_index < next_packet_index < boundary_index

print("RealMem closeout next Experience lane verification passed")
PY
