#!/usr/bin/env bash
# Offline verification for the MemoryArena no-write adapter contract.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER="$ROOT_DIR/scripts/memoryarena-adapter-contract.py"
REPORT="$ROOT_DIR/docs/reports/goal-c-u/2026-07-09-memoryarena-adapter-contract.md"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-memoryarena-contract-XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

fixture="$tmpdir/memoryarena"
store_db="$tmpdir/state.db"
output_json="$tmpdir/output.json"
mkdir -p \
  "$fixture/bundled_shopping" \
  "$fixture/formal_reasoning_math" \
  "$fixture/formal_reasoning_phys" \
  "$fixture/group_travel_planner" \
  "$fixture/progressive_search"

cat > "$fixture/bundled_shopping/data.jsonl" <<'JSONL'
{"id":0,"category":"fixture category","questions":["Find a quiet red boot option","Compare the shipping timing"],"answers":[{"sku":"private red boot answer"},{"timing":"private shipping answer"}]}
{"id":1,"category":"fixture category","questions":["Check whether the item is in stock"],"answers":[{"stock":"private stock answer"}]}
JSONL

cat > "$fixture/progressive_search/data.jsonl" <<'JSONL'
{"id":0,"questions":["Locate the first clue","Use the first clue for the second step","Finalize the chained lookup"],"answers":["first clue answer","second step answer","final lookup answer"]}
JSONL

cat > "$fixture/group_travel_planner/data.jsonl" <<'JSONL'
{"id":1,"base_person":{"name":"private traveler","preferences":["quiet mornings"]},"questions":["Choose a day plan","Adjust for the traveler's preference"],"answers":[["private day plan"],["private preference plan"]]}
JSONL

cat > "$fixture/formal_reasoning_math/data.jsonl" <<'JSONL'
{"id":0,"paper_name":"fixture math paper","backgrounds":["math background one",""],"questions":["Solve the first lemma","Use the lemma in the theorem"],"answers":["lemma answer","theorem answer"]}
JSONL

cat > "$fixture/formal_reasoning_phys/data.jsonl" <<'JSONL'
{"id":0,"paper_name":"fixture physics paper","backgrounds":["physics background"],"questions":["Explain the derived result"],"answers":["physics answer"]}
JSONL

python3 - "$store_db" <<'PY'
import sqlite3
import sys

db = sys.argv[1]
con = sqlite3.connect(db)
try:
    con.execute("CREATE TABLE memories (key TEXT PRIMARY KEY)")
    con.execute("CREATE TABLE memory_edges (from_key TEXT, to_key TEXT, edge_type TEXT)")
    con.execute("CREATE TABLE semantic_events (id INTEGER PRIMARY KEY)")
    con.execute("INSERT INTO memories (key) VALUES ('sentinel_memory')")
    con.execute("INSERT INTO memory_edges (from_key, to_key, edge_type) VALUES ('a','b','relates')")
    con.execute("INSERT INTO semantic_events (id) VALUES (1)")
    con.commit()
finally:
    con.close()
PY

python3 "$HELPER" \
  --source-dir "$fixture" \
  --store-db "$store_db" \
  --output "$output_json"

python3 - "$output_json" <<'PY'
import json
import re
import sys
from pathlib import Path

packet = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

assert packet["schema"] == "agent_bridge.memoryarena_adapter_contract.v0"
assert packet["shape_schema"] == "agent_bridge.memoryarena_task_shape_packet.v0"
assert packet["source_dataset"] == "https://huggingface.co/datasets/ZexueHe/memoryarena"
assert packet["source_project"] == "https://memoryarena.github.io/"
assert packet["source_paper"] == "https://arxiv.org/abs/2602.16313"
assert packet["source_revision"] == "da1a37c8b19280e18627ca01cf368195a5e1d92e"
assert packet["source_mode"] == "local_fixture"
assert packet["official_runner_import_allowed"] is False
assert packet["memoryarena_runner_allowed_now"] is False
assert packet["third_party_runtime_dependencies"] is False
assert packet["api_key_required"] is False
assert packet["private_memory_export_allowed"] is False
assert packet["writes_ab_store"] is False
assert packet["benchmark_performance_claim"] is False
assert packet["raw_content_in_output"] is False
assert packet["verdict"] == "PASS"
assert packet["scope"] == "benchmark:memoryarena"

assert set(packet["source_sha256"]) == {
    "bundled_shopping",
    "formal_reasoning_math",
    "formal_reasoning_phys",
    "group_travel_planner",
    "progressive_search",
}
assert all(re.fullmatch(r"[0-9a-f]{64}", value) for value in packet["source_sha256"].values())

identity = packet["identifier_contract"]
assert identity == {
    "stability_scope": "pinned_source_revision",
    "task_identity_input": "source_revision,config,canonical_json(source_id)",
    "task_identity_digest": "sha256_first_20_hex",
    "edge_identity_input": "logical_edge_kind,from_key,to_key",
    "edge_identity_digest": "sha256_first_24_hex",
    "templates": {
        "config": "memoryarena:{config}:config",
        "task": "memoryarena:{config}:task:{task_identity_digest}",
        "question": "{task_key}:question:{one_based_ordinal_4d}",
        "answer_reference": "{task_key}:answer:{one_based_ordinal_4d}",
        "background": "{task_key}:background:{one_based_ordinal_4d}",
        "base_person": "{task_key}:base-person",
        "edge": "memoryarena:edge:{logical_edge_kind}:{edge_identity_digest}",
    },
    "source_id_exposed": False,
}

records = packet["record_projection"]
assert records["record_kinds"] == [
    "benchmark_synthetic_memoryarena_config",
    "benchmark_synthetic_memoryarena_task",
    "benchmark_synthetic_memoryarena_question",
    "benchmark_synthetic_memoryarena_answer_reference",
    "benchmark_synthetic_memoryarena_background",
    "benchmark_synthetic_memoryarena_base_person",
]
assert records["record_kind_counts"] == {
    "benchmark_synthetic_memoryarena_answer_reference": 11,
    "benchmark_synthetic_memoryarena_background": 2,
    "benchmark_synthetic_memoryarena_base_person": 1,
    "benchmark_synthetic_memoryarena_config": 5,
    "benchmark_synthetic_memoryarena_question": 11,
    "benchmark_synthetic_memoryarena_task": 6,
}
assert records["projected_record_count"] == 36
assert records["unique_record_id_count"] == 36

edges = packet["edge_projection"]
assert edges["accepted_logical_edge_kinds"] == [
    "config_contains_task",
    "task_contains_question",
    "question_precedes_question",
    "question_answered_by",
    "background_supports_question",
    "base_person_supports_task",
]
assert edges["accepted_logical_edge_counts"] == {
    "background_supports_question": 2,
    "base_person_supports_task": 1,
    "config_contains_task": 6,
    "question_answered_by": 11,
    "question_precedes_question": 5,
    "task_contains_question": 11,
}
assert edges["accepted_memory_edge_count"] == 36
assert edges["unique_edge_id_count"] == 36

shape = packet["shape_parity"]
assert shape == {
    "accepted_projection_item_count": 72,
    "answer_count": 11,
    "answer_value_shapes": {"array": 2, "object": 3, "string": 6},
    "background_slot_count": 3,
    "base_person_count": 1,
    "base_person_value_shapes": {"object": 1},
    "config_count": 5,
    "empty_background_count": 1,
    "nonempty_background_count": 2,
    "question_count": 11,
    "row_count": 6,
    "temporary_edge_count": 36,
    "temporary_record_count": 36,
}

quality = packet["data_quality_flags"]
assert quality == {
    "duplicate_record_id_count": 0,
    "duplicate_edge_id_count": 0,
    "dangling_edge_endpoint_count": 0,
    "empty_backgrounds_not_projected": True,
    "heterogeneous_answer_shapes_preserved_as_metadata": True,
    "source_values_redacted": True,
}
assert all(packet["acceptance_gates"].values())

comparison = packet["adapter_family_comparison"]
assert comparison["reference_schema"] == "agent_bridge.realmem_adapter_contract.v0"
assert comparison["memoryarena_reference_resolver_required"] is False
assert comparison["realmem_reference_resolver_required"] is True
assert comparison["compatible_no_write_adapter_structure"] is True
assert comparison["runtime_compatibility_claim"] is False

record_samples = packet["samples"]["records"]
edge_samples = packet["samples"]["accepted_edges"]
assert [row["kind"] for row in record_samples] == records["record_kinds"]
assert [row["logical_edge_kind"] for row in edge_samples] == edges[
    "accepted_logical_edge_kinds"
]
assert len(record_samples) == 6
assert len(edge_samples) == 6
assert re.fullmatch(
    r"memoryarena:bundled_shopping:task:[0-9a-f]{20}",
    record_samples[1]["key"],
)
assert all(
    re.fullmatch(r"memoryarena:edge:[a-z_]+:[0-9a-f]{24}", row["id"])
    for row in edge_samples
)
assert all(row["scope"] == "benchmark:memoryarena" for row in record_samples)
assert all(
    row["content_policy"] == "source_content_redacted_from_packet"
    for row in record_samples
)

no_write = packet["no_write_invariant"]
assert no_write == {
    "checked": True,
    "passed": True,
    "before": {"memories": 1, "memory_edges": 1, "semantic_events": 1},
    "after": {"memories": 1, "memory_edges": 1, "semantic_events": 1},
    "deltas": {"memories": 0, "memory_edges": 0, "semantic_events": 0},
}

text = json.dumps(packet, sort_keys=True)
for raw in [
    "quiet red boot",
    "private red boot answer",
    "private traveler",
    "quiet mornings",
    "private day plan",
    "math background one",
    "physics answer",
    "chained lookup",
]:
    assert raw not in text

print("MemoryArena adapter contract fixture verification passed")
PY

duplicate_fixture="$tmpdir/memoryarena-duplicate"
duplicate_output="$tmpdir/duplicate-output.json"
cp -R "$fixture" "$duplicate_fixture"
cat >> "$duplicate_fixture/bundled_shopping/data.jsonl" <<'JSONL'
{"id":0,"category":"duplicate category","questions":["Duplicate first question","Duplicate second question"],"answers":[{"duplicate":"answer one"},{"duplicate":"answer two"}]}
JSONL

if python3 "$HELPER" \
  --source-dir "$duplicate_fixture" \
  --output "$duplicate_output"; then
  echo "expected duplicate source identity fixture to fail" >&2
  exit 1
fi

python3 - "$duplicate_output" <<'PY'
import json
import sys
from pathlib import Path

packet = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
assert packet["verdict"] == "FAIL"
assert packet["data_quality_flags"]["duplicate_record_id_count"] > 0
assert packet["data_quality_flags"]["duplicate_edge_id_count"] > 0
assert packet["acceptance_gates"]["record_ids_unique"] is False
assert packet["acceptance_gates"]["edge_ids_unique"] is False
assert packet["acceptance_gates"]["edge_endpoints_resolve"] is True
print("MemoryArena adapter duplicate-identity rejection passed")
PY

python3 - "$REPORT" <<'PY'
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
required = [
    "# MemoryArena Adapter Contract",
    "Source base commit: `b1cfd8f6`",
    "Run type: no-write adapter contract implementation",
    "memory_evolution_stage: experience_candidate",
    "experience_candidate_surface: adapter_contract_only",
    "runtime_authority: none",
    "promotion_allowed: false",
    "private_memory_export_allowed: false",
    "third_party_runtime_dependencies: false",
    "no_write_invariant: true",
    "memoryarena_adapter_contract_20260709",
    "codex-memoryarena-adapter-contract-20260709_active",
    "Forum thread: `design#119`, post `2994`",
    "memoryarena_follow_on_roadmap_20260709",
    "schema: agent_bridge.memoryarena_adapter_contract.v0",
    "shape_schema: agent_bridge.memoryarena_task_shape_packet.v0",
    "source_revision: da1a37c8b19280e18627ca01cf368195a5e1d92e",
    "scope: benchmark:memoryarena",
    "verdict: PASS",
    "official_runner_import_allowed: false",
    "memoryarena_runner_allowed_now: false",
    "third_party_runtime_dependencies: false",
    "api_key_required: false",
    "private_memory_export_allowed: false",
    "writes_ab_store: false",
    "benchmark_performance_claim: false",
    "raw_content_in_output: false",
    "task_identity_input: source_revision,config,canonical_json(source_id)",
    "task_identity_digest: sha256_first_20_hex",
    "edge_identity_digest: sha256_first_24_hex",
    "source_id_exposed: false",
    "projected_record_count: 10808",
    "unique_record_id_count: 10808",
    "accepted_memory_edge_count: 14952",
    "unique_edge_id_count: 14952",
    "accepted_projection_item_count: 25760",
    "duplicate_record_id_count: 0",
    "duplicate_edge_id_count: 0",
    "dangling_edge_endpoint_count: 0",
    "question_precedes_question: 4149",
    "background_supports_question: 132",
    "base_person_supports_task: 270",
    "agent_bridge.realmem_adapter_contract.v0",
    "memoryarena_reference_resolver_required: false",
    "realmem_reference_resolver_required: true",
    "compatible_no_write_adapter_structure: true",
    "runtime_compatibility_claim: false",
    "record_count_matches_shape_packet: true",
    "edge_count_matches_shape_packet: true",
    "record_ids_unique: true",
    "edge_ids_unique: true",
    "edge_endpoints_resolve: true",
    "raw_content_redacted: true",
    "no_ab_store_write: true",
    "no_benchmark_performance_claim: true",
    "no MemoryArena runner",
    "no dependency installation",
    "no private AB memory export",
    "no AB store writes",
    "no benchmark score or performance claim",
    "memoryarena_projection_integrity_gate",
]

missing = [needle for needle in required if needle not in text]
if missing:
    raise SystemExit("Missing MemoryArena adapter report anchors: " + ", ".join(missing))

for forbidden in [
    "writes_ab_store: true",
    "private_memory_export_allowed: true",
    "memoryarena_runner_allowed_now: true",
    "benchmark performance is proven",
    "MemoryArena evaluation passed",
    "installed dependencies",
]:
    assert forbidden not in text

schema_index = text.index("## Packet Contract")
identity_index = text.index("## Identifier Contract")
result_index = text.index("## Full Pinned Result")
comparison_index = text.index("## Adapter Family Comparison")
boundary_index = text.index("## Boundary")
next_index = text.index("## Next Step")
assert schema_index < identity_index < result_index < comparison_index
assert comparison_index < boundary_index < next_index

print("MemoryArena adapter contract report verification passed")
PY
