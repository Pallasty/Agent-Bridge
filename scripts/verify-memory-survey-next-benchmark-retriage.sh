#!/usr/bin/env bash
# Offline verification for the memory-survey next benchmark retriage packet.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPORT="$ROOT_DIR/docs/reports/goal-c-u/2026-07-09-memory-survey-next-benchmark-retriage.md"

python3 - "$REPORT" <<'PY'
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
text = report_path.read_text(encoding="utf-8")

required = [
    "# Memory Survey Next Benchmark Lane Retriage",
    "Source base commit: `076be559`",
    "Run type: docs-only benchmark-lane selection, no runner",
    "memory_evolution_stage: reflection",
    "runtime_authority: none",
    "promotion_allowed: false",
    "private_memory_export_allowed: false",
    "third_party_runtime_dependencies: false",
    "no_write_invariant: true",
    "structmemeval_status: locally_scaffolded",
    "selected_next_lane: realmem_dialogue_shape_packet",
    "selected_next_lane_stage: reflection_to_experience_candidate",
    "benchmark_performance_claim_allowed: false",
    "realmem_runner_allowed_now: false",
    "official_runner_import_allowed_now: false",
    "dependency_install_allowed_now: false",
    "private_memory_export_allowed: false",
    "writes_ab_store: false",
    "memory_survey_next_benchmark_retriage_20260709",
    "codex-memory-survey-next-benchmark-retriage-20260709_active",
    "structmemeval_next_lane_value_assessment_20260709",
    "docs/reports/goal-c-u/2026-07-09-memory-survey-benchmark-triage.md",
    "docs/reports/goal-c-u/2026-07-09-structmemeval-next-lane-value-assessment.md",
    "AvatarMemory/RealMemBench",
    "Apache-2.0",
    "dataset/Lin_Wanyu_dialogues_256k.json",
    "total_sessions: 207",
    "total_tokens: 227417",
    "dialogues_count: 207",
    "extracted_memory_count: 443",
    "query_turn_count: 126",
    "Memory Probe",
    "MemoryArena",
    "AMA-Bench",
    "MemoryBench",
    "LifelongAgentBench",
    "license unconfirmed",
    "no dependency installation",
    "no RealMem official eval runner",
    "no API-key-backed generation or judging",
    "no private AB memory export",
    "no AB store writes",
    "no benchmark score or performance claim",
]

missing = [needle for needle in required if needle not in text]
if missing:
    raise SystemExit("Missing required retriage anchors: " + ", ".join(missing))

for forbidden in [
    "benchmark score is ready",
    "benchmark performance is proven",
    "RealMem evaluation passed",
    "installed dependencies",
    "writes_ab_store=true",
    "private_memory_export_allowed: true",
    "realmem_runner_allowed_now: true",
]:
    assert forbidden not in text

decision_index = text.index("selected_next_lane: realmem_dialogue_shape_packet")
snapshot_index = text.index("## Source Snapshot")
next_step_index = text.index("## Next Step")
assert decision_index < snapshot_index < next_step_index

print("Memory survey next benchmark retriage verification passed")
PY
