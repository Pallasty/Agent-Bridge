#!/usr/bin/env bash
# Offline verification for the RealMem no-write adapter contract.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER="$ROOT_DIR/scripts/realmem-adapter-contract.py"
REPORT="$ROOT_DIR/docs/reports/goal-c-u/2026-07-09-realmem-adapter-contract-packet.md"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-realmem-contract-XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

fixture="$tmpdir/realmem-contract-fixture.json"
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
          "source_turn": 0,
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
          "query_id": null,
          "memory_used": [],
          "memory_session_uuids": [],
          "session_type": "single_session",
          "category_name": "Dynamic Incremental",
          "topic": "database study"
        },
        {
          "speaker": "Assistant",
          "content": "Understood. I will keep them concise.",
          "is_query": null,
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
          "content": {"topic": "indexes", "status": "reviewing"},
          "source_turn": -1,
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
          "query_id": null,
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

assert packet["schema"] == "agent_bridge.realmem_adapter_contract.v0"
assert packet["shape_schema"] == "agent_bridge.realmem_dialogue_shape_packet.v0"
assert packet["source_repo"] == "https://github.com/AvatarMemory/RealMemBench"
assert packet["source_head"] == "67afd0891d603adcc4458ff0449df306ef296b7a"
assert packet["scope"] == "benchmark:realmem"
assert packet["verdict"] == "PASS"
assert packet["official_runner_import_allowed"] is False
assert packet["realmem_runner_allowed_now"] is False
assert packet["third_party_runtime_dependencies"] is False
assert packet["api_key_required"] is False
assert packet["private_memory_export_allowed"] is False
assert packet["writes_ab_store"] is False
assert packet["benchmark_performance_claim"] is False
assert packet["raw_content_in_output"] is False

records = packet["record_projection"]
assert records["record_kinds"] == [
    "benchmark_synthetic_realmem_session",
    "benchmark_synthetic_realmem_turn",
    "benchmark_synthetic_realmem_extracted_memory",
    "benchmark_synthetic_realmem_query_turn",
]
assert records["record_kind_counts"] == {
    "benchmark_synthetic_realmem_extracted_memory": 2,
    "benchmark_synthetic_realmem_query_turn": 1,
    "benchmark_synthetic_realmem_session": 2,
    "benchmark_synthetic_realmem_turn": 4,
}
assert records["projected_record_count"] == 9

edges = packet["edge_projection"]
assert edges["accepted_logical_edge_counts"] == {
    "chronologically_before": 1,
    "contains_extracted_memory": 2,
    "contains_turn": 4,
    "derived_from_source_turn": 1,
    "query_turn_record": 1,
    "uses_memory_session": 2,
}
assert edges["accepted_memory_edge_count"] == 11
assert edges["unresolved_reference_counts"] == {
    "memory_used_content_reference": 2,
    "source_turn_indexing_reference": 0,
}
assert edges["unresolved_reference_count"] == 2
assert edges["edge_candidate_count"] == 13

quality = packet["data_quality_flags"]
assert quality["non_bool_is_query_count"] == 1
assert quality["non_string_memory_content_count"] == 1
assert quality["source_turn_unresolved_count"] == 1
assert quality["source_turn_negative_count"] == 1
assert quality["source_turn_indexing_reference_count"] == 0
assert quality["memory_used_content_reference_count"] == 2
assert quality["memory_used_requires_resolver"] is True
assert quality["memory_content_shape_counts"] == {"object": 1, "string": 1}

gates = packet["acceptance_gates"]
assert gates == {
    "accepted_edges_exclude_memory_used_content_refs": True,
    "edge_candidate_count_matches_shape_packet": True,
    "no_ab_store_write": True,
    "no_benchmark_performance_claim": True,
    "raw_content_redacted": True,
    "record_count_matches_shape_packet": True,
    "shape_schema_matches": True,
    "source_pinned": True,
}

proof = packet["no_write_invariant"]
assert proof == {
    "checked": True,
    "passed": True,
    "memory_rows_delta": 0,
    "memory_edges_delta": 0,
    "semantic_events_delta": 0,
}

assert packet["samples"]["records"]
assert packet["samples"]["accepted_edges"]
assert packet["samples"]["unresolved_references"]
assert all(row["scope"] == "benchmark:realmem" for row in packet["samples"]["records"])
assert packet["samples"]["unresolved_references"][0]["blocking_real_eval"] is True

for session in fixture["dialogues"]:
    assert session["current_time"] not in text
    for memory in session["extracted_memory"]:
        if isinstance(memory["content"], str):
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

print("RealMem adapter contract verification passed")
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
    "# RealMem Adapter Contract Packet",
    "Source base commit: `26527973`",
    "Run type: no-write adapter contract implementation",
    "memory_evolution_stage: reflection",
    "experience_candidate_surface: adapter_contract_only",
    "runtime_authority: none",
    "promotion_allowed: false",
    "private_memory_export_allowed: false",
    "third_party_runtime_dependencies: false",
    "no_write_invariant: true",
    "realmem_adapter_contract_packet_20260709",
    "codex-realmem-adapter-contract-20260709_active",
    "realmem_dialogue_shape_packet_20260709",
    "67afd0891d603adcc4458ff0449df306ef296b7a",
    "Apache-2.0",
    "schema: agent_bridge.realmem_adapter_contract.v0",
    "shape_schema: agent_bridge.realmem_dialogue_shape_packet.v0",
    "official_runner_import_allowed: false",
    "realmem_runner_allowed_now: false",
    "third_party_runtime_dependencies: false",
    "api_key_required: false",
    "private_memory_export_allowed: false",
    "writes_ab_store: false",
    "benchmark_performance_claim: false",
    "raw_content_in_output: false",
    "benchmark_synthetic_realmem_session: 207",
    "benchmark_synthetic_realmem_turn: 1284",
    "benchmark_synthetic_realmem_extracted_memory: 443",
    "benchmark_synthetic_realmem_query_turn: 126",
    "projected_record_count: 2060",
    "accepted_memory_edge_count: 2703",
    "memory_used_content_reference: 327",
    "source_turn_indexing_reference: 30",
    "unresolved_reference_count: 357",
    "edge_candidate_count: 3060",
    "verdict: PASS",
    "source_sha256: a7a751066c48e829b3012a94f2b365febd0e6fb6db454a6d5f4ec01f9c55008a",
    "record_count_matches_shape_packet: true",
    "edge_candidate_count_matches_shape_packet: true",
    "source_turn_unresolved_count: 37",
    "source_turn_negative_count: 7",
    "source_turn_indexing_reference_count: 30",
    "memory_used_requires_resolver: true",
    "memory_rows_delta: 0",
    "memory_edges_delta: 0",
    "semantic_events_delta: 0",
    "realmem_reference_resolver_packet",
]

missing = [needle for needle in required if needle not in text]
if missing:
    raise SystemExit("Missing required RealMem adapter report anchors: " + ", ".join(missing))

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
projection_index = text.index("## Projection Contract")
boundary_index = text.index("## Boundary")
next_step_index = text.index("## Next Step")
assert verdict_index < projection_index < boundary_index < next_step_index

print("RealMem adapter contract report verification passed")
PY
