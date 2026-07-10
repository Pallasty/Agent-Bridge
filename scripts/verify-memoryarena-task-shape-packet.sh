#!/usr/bin/env bash
# Offline verification for the MemoryArena task shape packet.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER="$ROOT_DIR/scripts/memoryarena-task-shape-inspector.py"
REPORT="$ROOT_DIR/docs/reports/goal-c-u/2026-07-09-memoryarena-task-shape-packet.md"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-memoryarena-shape-XXXXXX")"
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
{"id":0,"category":"fixture category","questions":["Find a quiet red boot option","Compare the shipping timing"],"answers":["red boot answer","shipping answer"]}
{"id":1,"category":"fixture category","questions":["Check whether the item is in stock"],"answers":["stock answer"]}
JSONL

cat > "$fixture/progressive_search/data.jsonl" <<'JSONL'
{"id":0,"questions":["Locate the first clue","Use the first clue for the second step","Finalize the chained lookup"],"answers":["first clue answer","second step answer","final lookup answer"]}
JSONL

cat > "$fixture/group_travel_planner/data.jsonl" <<'JSONL'
{"id":1,"base_person":"fixture traveler profile","questions":["Choose a day plan","Adjust for the traveler's preference"],"answers":["day plan answer","preference answer"]}
JSONL

cat > "$fixture/formal_reasoning_math/data.jsonl" <<'JSONL'
{"id":0,"paper_name":"fixture math paper","backgrounds":["math background one","math background two"],"questions":["Solve the first lemma","Use the lemma in the theorem"],"answers":["lemma answer","theorem answer"]}
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
import sys
from pathlib import Path

packet = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

assert packet["schema"] == "agent_bridge.memoryarena_task_shape_packet.v0"
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

assert packet["config_order"] == [
    "bundled_shopping",
    "formal_reasoning_math",
    "formal_reasoning_phys",
    "group_travel_planner",
    "progressive_search",
]

summary = packet["summary"]
assert summary == {
    "accepted_projection_item_count": 74,
    "answer_count": 11,
    "background_count": 3,
    "background_slot_count": 3,
    "background_length_mismatch_count": 0,
    "base_person_count": 1,
    "config_count": 5,
    "empty_answer_count": 0,
    "empty_background_count": 0,
    "nonempty_background_count": 3,
    "qa_length_mismatch_count": 0,
    "question_count": 11,
    "row_count": 6,
    "temporary_edge_count": 37,
    "temporary_record_count": 37,
}

fields = packet["field_inventory"]
assert fields["optional_field_presence"] == {
    "backgrounds": 2,
    "base_person": 1,
    "category": 2,
    "paper_name": 2,
}
assert fields["key_shapes"] == {
    "answers,backgrounds,id,paper_name,questions": 2,
    "answers,base_person,id,questions": 1,
    "answers,category,id,questions": 2,
    "answers,id,questions": 1,
}
assert fields["answer_value_shapes"] == {"string": 11}
assert fields["background_value_shapes"] == {"string": 3}
assert fields["base_person_value_shapes"] == {"string": 1}

bundled = packet["configs"]["bundled_shopping"]
assert bundled["row_count"] == 2
assert bundled["question_count"] == 3
assert bundled["answer_count"] == 3
assert bundled["background_count"] == 0
assert bundled["question_count_distribution"] == {"1": 1, "2": 1}
assert bundled["answer_value_shapes"] == {"string": 3}
assert bundled["projection"]["temporary_record_count"] == 9
assert bundled["projection"]["temporary_edge_count"] == 9

math = packet["configs"]["formal_reasoning_math"]
assert math["background_count"] == 2
assert math["background_count_distribution"] == {"2": 1}
assert math["answer_value_shapes"] == {"string": 2}
assert math["background_value_shapes"] == {"string": 2}
assert math["projection"]["background_supports_question_edges"] == 2

group = packet["configs"]["group_travel_planner"]
assert group["base_person_count"] == 1
assert group["answer_value_shapes"] == {"string": 2}
assert group["base_person_value_shapes"] == {"string": 1}
assert group["projection"]["base_person_supports_task_edges"] == 1

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
    "fixture traveler profile",
    "math background one",
    "physics answer",
    "chained lookup",
]:
    assert raw not in text

print("MemoryArena task shape fixture verification passed")
PY

python3 - "$REPORT" <<'PY'
import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text(encoding="utf-8")
required = [
    "# MemoryArena Task Shape Packet",
    "Source base commit: `638a7896`",
    "Run type: local MemoryArena task-shape inspection, no runner",
    "memory_evolution_stage: experience_candidate",
    "runtime_authority: none",
    "promotion_allowed: false",
    "private_memory_export_allowed: false",
    "third_party_runtime_dependencies: false",
    "no_write_invariant: true",
    "memoryarena_task_shape_packet_20260709",
    "codex-memoryarena-task-shape-packet-20260709_active",
    "Forum thread: `design#119`, post `2992`",
    "realmem_closeout_next_experience_lane_20260709",
    "agent_bridge.memoryarena_task_shape_packet.v0",
    "ZexueHe/memoryarena",
    "da1a37c8b19280e18627ca01cf368195a5e1d92e",
    "CC-BY-4.0",
    "total_rows: 701",
    "config_count: 5",
    "question_count: 4850",
    "answer_count: 4850",
    "background_slot_count: 440",
    "nonempty_background_count: 132",
    "empty_background_count: 308",
    "base_person_count: 270",
    "answer_value_shapes:",
    "object: 900",
    "array: 1869",
    "string: 2081",
    "base_person_value_shapes:",
    "object: 270",
    "temporary_record_count: 10808",
    "temporary_edge_count: 14952",
    "accepted_projection_item_count: 25760",
    "qa_length_mismatch_count: 0",
    "background_length_mismatch_count: 0",
    "bundled_shopping:",
    "row_count: 150",
    "group_travel_planner:",
    "row_count: 270",
    "progressive_search:",
    "row_count: 221",
    "formal_reasoning_math:",
    "row_count: 40",
    "formal_reasoning_phys:",
    "row_count: 20",
    "no MemoryArena runner",
    "no dependency installation",
    "no API-key-backed generation or judging",
    "no private AB memory export",
    "no AB store writes",
    "no benchmark score or performance claim",
]

missing = [needle for needle in required if needle not in text]
if missing:
    raise SystemExit("Missing required MemoryArena report anchors: " + ", ".join(missing))

for forbidden in [
    "benchmark score is ready",
    "benchmark performance is proven",
    "MemoryArena evaluation passed",
    "installed dependencies",
    "writes_ab_store: true",
    "private_memory_export_allowed: true",
    "memoryarena_runner_allowed_now: true",
]:
    assert forbidden not in text

schema_index = text.index("## Packet Schema")
observed_index = text.index("## Observed Full-Shape Result")
projection_index = text.index("## Temporary Projection Contract")
boundary_index = text.index("## Boundary")
assert schema_index < observed_index < projection_index < boundary_index

print("MemoryArena task shape report verification passed")
PY
