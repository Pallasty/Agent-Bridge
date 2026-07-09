#!/usr/bin/env bash
# Offline verification for the RealMem dialogue shape inspector.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER="$ROOT_DIR/scripts/realmem-dialogue-shape-inspector.py"
REPORT="$ROOT_DIR/docs/reports/goal-c-u/2026-07-09-realmem-dialogue-shape-packet.md"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-realmem-shape-XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

fixture="$tmpdir/realmem-fixture.json"
store_db="$tmpdir/state.db"
output_json="$tmpdir/output.json"

cat > "$fixture" <<'JSON'
{
  "_metadata": {
    "person_name": "Lin_Wanyu",
    "total_sessions": 2,
    "total_tokens": 1234
  },
  "dialogues": [
    {
      "session_identifier": "Knowledge_Learning_1:S1_01",
      "session_uuid": "session-001",
      "current_time": "2026-01-01 09:00",
      "extracted_memory": [
        {
          "index": "Knowledge_Learning_1-DM-S1_01-01",
          "type": "Dynamic",
          "content": "Lin Wanyu prefers concise database study notes.",
          "source_turn": 1,
          "source_content_snapshot": "Please keep database study notes concise.",
          "source_role_snapshot": "User",
          "session_uuid": "session-001"
        }
      ],
      "dialogue_turns": [
        {
          "speaker": "User",
          "content": "Please keep database study notes concise.",
          "is_query": false,
          "query_id": "",
          "memory_used": [],
          "memory_session_uuids": [],
          "session_type": "single_session",
          "category_name": "Dynamic Incremental",
          "topic": "database study"
        },
        {
          "speaker": "Assistant",
          "content": "Understood. I will keep them concise.",
          "is_query": false,
          "query_id": "",
          "memory_used": [],
          "memory_session_uuids": [],
          "session_type": "single_session",
          "category_name": "Dynamic Incremental",
          "topic": "database study"
        }
      ]
    },
    {
      "session_identifier": "Knowledge_Learning_1:S1_02",
      "session_uuid": "session-002",
      "current_time": "2026-01-02 09:00",
      "extracted_memory": [
        {
          "index": "Knowledge_Learning_1-DM-S1_02-01",
          "type": "Static",
          "content": "Lin Wanyu is reviewing indexes.",
          "source_turn": 1,
          "source_content_snapshot": "Can you remind me how indexes work?",
          "source_role_snapshot": "User",
          "session_uuid": "session-002"
        }
      ],
      "dialogue_turns": [
        {
          "speaker": "User",
          "content": "Can you remind me how indexes work?",
          "is_query": true,
          "query_id": "Q-001",
          "memory_used": [
            {
              "session_uuid": "session-001",
              "content": "Lin Wanyu prefers concise database study notes."
            }
          ],
          "memory_session_uuids": ["session-001"],
          "session_type": "multi_session",
          "category_name": "Temporal-reasoning",
          "topic": "database study"
        },
        {
          "speaker": "Assistant",
          "content": "Indexes speed lookups by maintaining an ordered lookup structure.",
          "is_query": false,
          "query_id": "",
          "memory_used": [
            {
              "session_uuid": "session-001",
              "content": "Lin Wanyu prefers concise database study notes."
            }
          ],
          "memory_session_uuids": ["session-001"],
          "session_type": "multi_session",
          "category_name": "Temporal-reasoning",
          "topic": "database study"
        }
      ]
    }
  ]
}
JSON

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
  --source "$fixture" \
  --store-db "$store_db" \
  --output "$output_json"

python3 - "$output_json" "$fixture" <<'PY'
import json
import sys
from pathlib import Path

output_path = Path(sys.argv[1])
fixture_path = Path(sys.argv[2])
text = output_path.read_text(encoding="utf-8")
packet = json.loads(text)
fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

assert packet["schema"] == "agent_bridge.realmem_dialogue_shape_packet.v0"
assert packet["source_repo"] == "https://github.com/AvatarMemory/RealMemBench"
assert packet["source_head"] == "67afd0891d603adcc4458ff0449df306ef296b7a"
assert packet["official_runner_import_allowed"] is False
assert packet["realmem_runner_allowed_now"] is False
assert packet["third_party_runtime_dependencies"] is False
assert packet["api_key_required"] is False
assert packet["private_memory_export_allowed"] is False
assert packet["writes_ab_store"] is False
assert packet["benchmark_performance_claim"] is False
assert packet["raw_content_in_output"] is False

assert packet["person"] == {
    "person_name": "Lin_Wanyu",
    "total_sessions": 2,
    "total_tokens": 1234,
}
summary = packet["summary"]
assert summary["session_count"] == 2
assert summary["turn_count"] == 4
assert summary["query_turn_count"] == 1
assert summary["non_bool_is_query_count"] == 0
assert summary["extracted_memory_count"] == 2
assert summary["empty_extracted_memory_content_count"] == 0
assert summary["source_turn_reference_count"] == 2
assert summary["memory_used_turn_count"] == 2
assert summary["memory_session_uuid_turn_count"] == 2
assert summary["memory_used_reference_count"] == 2
assert summary["memory_session_uuid_reference_count"] == 2
assert summary["temporary_record_count"] == 9
assert summary["temporary_edge_count"] == 14

fields = packet["field_inventory"]
assert fields["speaker_counts"] == {"Assistant": 2, "User": 2}
assert fields["is_query_shapes"] == {"bool": 4}
assert fields["memory_type_counts"] == {"Dynamic": 1, "Static": 1}
assert fields["extracted_memory_content_shapes"] == {"string": 2}
assert fields["session_type_counts"] == {"multi_session": 2, "single_session": 2}
assert fields["category_counts"] == {"Dynamic Incremental": 2, "Temporal-reasoning": 2}
assert fields["session_fields"] == [
    "current_time",
    "dialogue_turns",
    "extracted_memory",
    "session_identifier",
    "session_uuid",
]
assert fields["turn_fields"] == [
    "category_name",
    "content",
    "is_query",
    "memory_session_uuids",
    "memory_used",
    "query_id",
    "session_type",
    "speaker",
    "topic",
]
assert fields["extracted_memory_fields"] == [
    "content",
    "index",
    "session_uuid",
    "source_content_snapshot",
    "source_role_snapshot",
    "source_turn",
    "type",
]

contract = packet["projection_contract"]
assert contract["memory_record_kinds"] == [
    "benchmark_synthetic_persona_session",
    "benchmark_synthetic_dialogue_turn",
    "benchmark_synthetic_extracted_memory",
    "benchmark_synthetic_query_turn",
]
assert contract["edge_type_counts"] == {
    "chronologically_before": 1,
    "contains_extracted_memory": 2,
    "contains_turn": 4,
    "derived_from_source_turn": 2,
    "query_turn_record": 1,
    "uses_memory": 2,
    "uses_memory_session": 2,
}

proof = packet["no_write_invariant"]
assert proof == {
    "checked": True,
    "passed": True,
    "memory_rows_delta": 0,
    "memory_edges_delta": 0,
    "semantic_events_delta": 0,
}

for session in fixture["dialogues"]:
    assert session["current_time"] not in text
    for memory in session["extracted_memory"]:
        assert memory["content"] not in text
        assert memory["source_content_snapshot"] not in text
    for turn in session["dialogue_turns"]:
        assert turn["content"] not in text
        for memory_ref in turn["memory_used"]:
            assert memory_ref["content"] not in text
for disallowed in [
    '"content":',
    "benchmark performance",
    "RealMem evaluation passed",
    "installed dependencies",
    "writes_ab_store=true",
]:
    assert disallowed not in text

print("RealMem dialogue shape packet verification passed")
PY

if python3 "$HELPER" \
  --source "https://raw.githubusercontent.com/AvatarMemory/RealMemBench/main/dataset/Lin_Wanyu_dialogues_256k.json" \
  --output "$tmpdir/unpinned.json" > "$tmpdir/stdout-unpinned" 2> "$tmpdir/stderr-unpinned"; then
  echo "expected unpinned URL to fail" >&2
  exit 1
fi
grep -q "URL must be pinned" "$tmpdir/stderr-unpinned"

python3 - "$REPORT" <<'PY'
import sys
from pathlib import Path

report_path = Path(sys.argv[1])
text = report_path.read_text(encoding="utf-8")

required = [
    "# RealMem Dialogue Shape Packet",
    "Source base commit: `ec7e2ab6`",
    "Run type: standard-library shape inspection, no RealMem runner",
    "memory_evolution_stage: reflection",
    "experience_candidate_surface: shape_only",
    "runtime_authority: none",
    "promotion_allowed: false",
    "private_memory_export_allowed: false",
    "third_party_runtime_dependencies: false",
    "no_write_invariant: true",
    "realmem_dialogue_shape_packet_20260709",
    "codex-realmem-dialogue-shape-20260709_active",
    "memory_survey_next_benchmark_retriage_20260709",
    "67afd0891d603adcc4458ff0449df306ef296b7a",
    "Apache-2.0",
    "dataset/Lin_Wanyu_dialogues_256k.json",
    "schema: agent_bridge.realmem_dialogue_shape_packet.v0",
    "official_runner_import_allowed: false",
    "realmem_runner_allowed_now: false",
    "third_party_runtime_dependencies: false",
    "api_key_required: false",
    "private_memory_export_allowed: false",
    "writes_ab_store: false",
    "benchmark_performance_claim: false",
    "raw_content_in_output: false",
    "source_sha256: a7a751066c48e829b3012a94f2b365febd0e6fb6db454a6d5f4ec01f9c55008a",
    "session_count: 207",
    "turn_count: 1284",
    "query_turn_count: 126",
    "non_bool_is_query_count: 1",
    "extracted_memory_count: 443",
    "temporary_record_count: 2060",
    "temporary_edge_count: 3060",
    "is_query_shapes:",
    "extracted_memory_content_shapes:",
    "memory_rows_delta: 0",
    "memory_edges_delta: 0",
    "semantic_events_delta: 0",
    "benchmark_synthetic_persona_session",
    "uses_memory_session",
    "realmem_adapter_contract_packet",
]

missing = [needle for needle in required if needle not in text]
if missing:
    raise SystemExit("Missing required RealMem report anchors: " + ", ".join(missing))

for forbidden in [
    "RealMem benchmark score is ready",
    "RealMem evaluation passed",
    "benchmark performance is proven",
    "installed dependencies",
    "writes_ab_store=true",
    "private_memory_export_allowed: true",
    "realmem_runner_allowed_now: true",
]:
    assert forbidden not in text

verdict_index = text.index("## Verdict")
sample_index = text.index("## Pinned Sample Result")
boundary_index = text.index("## Boundary")
next_step_index = text.index("## Next Step")
assert verdict_index < sample_index < boundary_index < next_step_index

print("RealMem dialogue shape report verification passed")
PY
