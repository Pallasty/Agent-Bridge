#!/usr/bin/env bash
# Offline verification for the StructMemEval next-lane value assessment.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPORT="$ROOT_DIR/docs/reports/goal-c-u/2026-07-09-structmemeval-next-lane-value-assessment.md"

python3 - "$REPORT" <<'PY'
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
text = report_path.read_text(encoding="utf-8")

required = [
    "# StructMemEval Next-Lane Value Assessment",
    "Source base commit: `7e932279`",
    "Run type: docs-only value assessment, no benchmark runner",
    "memory_evolution_stage: reflection",
    "runtime_authority: none",
    "promotion_allowed: false",
    "private_memory_export_allowed: false",
    "third_party_runtime_dependencies: false",
    "no_write_invariant: true",
    "recommended_next_lane: pause_structmemeval_and_return_to_survey_triage",
    "real_runner_gate: owner_gated_boundary_packet_only",
    "benchmark_performance_claim_allowed: false",
    "official_runner_import_allowed_now: false",
    "dependency_install_allowed_now: false",
    "writes_ab_store: false",
    "private_memory_export_allowed: false",
    "structmemeval_next_lane_value_assessment_20260709",
    "codex-structmemeval-next-lane-assessment-20260709_active",
    "structmemeval_accounting_corpus_gate_20260709",
    "docs/reports/goal-c-u/2026-07-09-structmemeval-accounting-corpus-gate.md",
    "memory_survey_next_benchmark_lane_retriage",
    "structmemeval_real_runner_boundary_packet",
    "no dependency installation",
    "no external runner import",
    "no private AB memory export",
    "no benchmark-performance claim",
    "no MCP tool or runtime path",
]

missing = [needle for needle in required if needle not in text]
if missing:
    raise SystemExit("Missing required assessment anchors: " + ", ".join(missing))

for forbidden in [
    "benchmark score is ready",
    "benchmark performance is proven",
    "official runner was executed",
    "installed dependencies",
    "writes_ab_store=true",
    "private_memory_export_allowed: true",
]:
    assert forbidden not in text

decision_index = text.index("recommended_next_lane: pause_structmemeval_and_return_to_survey_triage")
boundary_index = text.index("## Boundary")
next_step_index = text.index("## Next Step")
assert decision_index < boundary_index < next_step_index

print("StructMemEval next-lane value assessment verification passed")
PY
