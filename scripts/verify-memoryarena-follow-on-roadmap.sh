#!/usr/bin/env bash
# Verify the MemoryArena follow-on roadmap and its admission boundaries.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPORT="$ROOT_DIR/docs/reports/goal-c-u/2026-07-09-memoryarena-follow-on-roadmap.md"

python3 - "$REPORT" <<'PY'
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")

required = [
    "# MemoryArena Follow-on Roadmap",
    "Source base commit: `50d639da`",
    "Run type: docs-first roadmap and implementation admission plan, no runner",
    "memory_evolution_stage: reflection",
    "runtime_authority: none",
    "promotion_allowed: false",
    "private_memory_export_allowed: false",
    "third_party_runtime_dependencies: false",
    "no_write_invariant: true",
    "codex-memoryarena-follow-on-roadmap-20260709_active",
    "Forum thread: `design#119`, post `2994`",
    "memoryarena_task_shape_packet_20260709",
    "selected_now: memoryarena_adapter_contract",
    "next_local_gate: memoryarena_projection_integrity_gate",
    "runner_review_gate: memoryarena_runner_boundary_packet",
    "real_runner_status: explicit_score_objective_required",
    "horizontal_follow_up: ama_bench_interface_shape_packet",
    "fallback_if_memoryarena_blocks: ama_bench_interface_shape_packet",
    "## Value And Priority",
    "| P0 | `memoryarena_adapter_contract`",
    "| P1 | `memoryarena_projection_integrity_gate`",
    "| P2 | `ama_bench_interface_shape_packet`",
    "| P2 | `memoryarena_runner_boundary_packet`",
    "| HOLD | `memoryarena_real_runner_execution`",
    "## Dependency Graph",
    "### P0: Adapter Contract",
    "### P1: Projection Integrity Gate",
    "### P2: Runner Boundary Packet",
    "### P3: Real Runner Execution",
    "record_count_matches_shape_packet: true",
    "edge_count_matches_shape_packet: true",
    "record_ids_unique: true",
    "edge_ids_unique: true",
    "edge_endpoints_resolve: true",
    "raw_content_redacted: true",
    "no_ab_store_write: true",
    "no_benchmark_performance_claim: true",
    "explicit request for benchmark scores",
    "## In-turn Implementation Scope",
    "## Replan Triggers",
    "install or execute the runner",
]

missing = [needle for needle in required if needle not in text]
if missing:
    raise SystemExit("Missing MemoryArena roadmap anchors: " + ", ".join(missing))

for forbidden in [
    "dependency_install_allowed_now: true",
    "official_runner_import_allowed_now: true",
    "private_memory_export_allowed: true",
    "writes_ab_store: true",
    "benchmark_performance_claim_allowed: true",
    "MemoryArena evaluation passed",
    "benchmark performance is proven",
]:
    assert forbidden not in text

decision_index = text.index("## Decision")
priority_index = text.index("## Value And Priority")
dependency_index = text.index("## Dependency Graph")
gates_index = text.index("## Packet Gates")
scope_index = text.index("## In-turn Implementation Scope")
replan_index = text.index("## Replan Triggers")
next_index = text.index("## Next Step")
assert decision_index < priority_index < dependency_index < gates_index
assert gates_index < scope_index < replan_index < next_index

p0_index = text.index("### P0: Adapter Contract")
p1_index = text.index("### P1: Projection Integrity Gate")
p2_index = text.index("### P2: Runner Boundary Packet")
p3_index = text.index("### P3: Real Runner Execution")
assert p0_index < p1_index < p2_index < p3_index

print("MemoryArena follow-on roadmap verification passed")
PY
