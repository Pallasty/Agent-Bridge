#!/usr/bin/env bash
# Offline verification for the RealMem resolved projection gate.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER="$ROOT_DIR/scripts/realmem-resolved-projection-gate.py"
REPORT="$ROOT_DIR/docs/reports/goal-c-u/2026-07-09-realmem-resolved-projection-gate.md"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-realmem-gate-XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

fixture="$tmpdir/realmem-gate-fixture.json"
store_db="$tmpdir/state.db"
output_json="$tmpdir/output.json"

cat > "$fixture" <<'JSON'
{
  "_metadata": {
    "person_name": "Lin_Wanyu",
    "total_sessions": 3,
    "total_tokens": 2345
  },
  "dialogues": [
    {
      "session_identifier": "Study:S1",
      "session_uuid": "session-001",
      "current_time": "2026-01-01 09:00",
      "extracted_memory": [
        {
          "index": "Study-S1-M1",
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
          "is_query": false,
          "query_id": null,
          "memory_used": [],
          "memory_session_uuids": [],
          "session_type": "single_session",
          "category_name": "Dynamic Incremental",
          "topic": "database study"
        }
      ]
    },
    {
      "session_identifier": "Study:S2",
      "session_uuid": "session-002",
      "current_time": "2026-01-02 09:00",
      "extracted_memory": [
        {
          "index": "Study-S2-M1",
          "type": "Static",
          "content": "Lin Wanyu is reviewing indexes.",
          "source_turn": 2,
          "source_content_snapshot": "Can you remind me how indexes work?",
          "source_role_snapshot": "User",
          "session_uuid": "session-002"
        },
        {
          "index": "Study-S2-M2",
          "type": "Schedule",
          "content": {"topic": "indexes", "status": "reviewing"},
          "source_turn": -1,
          "source_content_snapshot": "",
          "source_role_snapshot": "Assistant",
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
    },
    {
      "session_identifier": "Study:S3",
      "session_uuid": "session-003",
      "current_time": "2026-01-03 09:00",
      "extracted_memory": [
        {
          "index": "Study-S3-M1",
          "type": "Dynamic",
          "content": "Unique project note.",
          "source_turn": 0,
          "source_content_snapshot": "Remember this unique project note.",
          "source_role_snapshot": "User",
          "session_uuid": "session-003"
        }
      ],
      "dialogue_turns": [
        {
          "speaker": "User",
          "content": "Remember this unique project note.",
          "is_query": false,
          "query_id": null,
          "memory_used": [],
          "memory_session_uuids": [],
          "session_type": "single_session",
          "category_name": "Dynamic Incremental",
          "topic": "project note"
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

assert packet["schema"] == "agent_bridge.realmem_resolved_projection_gate.v0"
assert packet["shape_schema"] == "agent_bridge.realmem_dialogue_shape_packet.v0"
assert packet["adapter_schema"] == "agent_bridge.realmem_adapter_contract.v0"
assert packet["resolver_schema"] == "agent_bridge.realmem_reference_resolver.v0"
assert packet["source_repo"] == "https://github.com/AvatarMemory/RealMemBench"
assert packet["source_head"] == "67afd0891d603adcc4458ff0449df306ef296b7a"
assert packet["verdict"] == "PASS"
assert packet["official_runner_import_allowed"] is False
assert packet["realmem_runner_allowed_now"] is False
assert packet["third_party_runtime_dependencies"] is False
assert packet["api_key_required"] is False
assert packet["private_memory_export_allowed"] is False
assert packet["writes_ab_store"] is False
assert packet["benchmark_performance_claim"] is False
assert packet["raw_content_in_output"] is False

final = packet["final_projection"]
assert final == {
    "accepted_projection_item_count": 32,
    "adapter_accepted_edge_count": 16,
    "adapter_edge_candidate_count": 19,
    "final_accepted_edge_count": 19,
    "projected_record_count": 13,
    "residual_unresolved_count": 1,
    "residual_unresolved_counts": {
        "memory_used_ambiguous": 0,
        "memory_used_bad_shape": 0,
        "memory_used_missing": 0,
        "source_turn_negative": 1,
        "source_turn_out_of_range": 0,
    },
    "resolved_reference_count": 5,
    "resolver_added_fallback_source_turn_edges": 1,
    "resolver_added_memory_used_edges": 2,
}

gates = packet["acceptance_gates"]
assert gates == {
    "adapter_schema_matches": True,
    "adapter_verdict_pass": True,
    "final_accepted_edges_match_adapter_candidates": True,
    "memory_used_fully_resolved": True,
    "no_ab_store_write": True,
    "no_benchmark_performance_claim": True,
    "raw_content_redacted": True,
    "record_count_matches_adapter": True,
    "residual_unresolved_only_negative_source_turn": True,
    "resolver_schema_matches": True,
    "resolver_verdict_pass": True,
    "shape_schema_matches": True,
    "source_pinned": True,
    "source_turn_indexing_fully_resolved": True,
}

proof = packet["no_write_invariant"]
assert proof == {
    "checked": True,
    "passed": True,
    "memory_rows_delta": 0,
    "memory_edges_delta": 0,
    "semantic_events_delta": 0,
}

assert packet["samples"]["accepted_edges"]
assert packet["samples"]["residual_unresolved_references"][0]["reference_kind"] == "source_turn_negative"

for session in fixture["dialogues"]:
    assert session["current_time"] not in text
    for memory in session["extracted_memory"]:
        if isinstance(memory["content"], str):
            assert memory["content"] not in text
        if memory["source_content_snapshot"]:
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

print("RealMem resolved projection gate verification passed")
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
    "# RealMem Resolved Projection Gate",
    "Source base commit: `a414a83a`",
    "Run type: local resolved projection gate, no RealMem runner",
    "memory_evolution_stage: reflection",
    "experience_candidate_surface: resolved_projection_gate_only",
    "runtime_authority: none",
    "promotion_allowed: false",
    "private_memory_export_allowed: false",
    "third_party_runtime_dependencies: false",
    "no_write_invariant: true",
    "realmem_resolved_projection_gate_20260709",
    "codex-realmem-resolved-projection-gate-20260709_active",
    "realmem_reference_resolver_packet_20260709",
    "67afd0891d603adcc4458ff0449df306ef296b7a",
    "Apache-2.0",
    "schema: agent_bridge.realmem_resolved_projection_gate.v0",
    "shape_schema: agent_bridge.realmem_dialogue_shape_packet.v0",
    "adapter_schema: agent_bridge.realmem_adapter_contract.v0",
    "resolver_schema: agent_bridge.realmem_reference_resolver.v0",
    "official_runner_import_allowed: false",
    "realmem_runner_allowed_now: false",
    "third_party_runtime_dependencies: false",
    "api_key_required: false",
    "private_memory_export_allowed: false",
    "writes_ab_store: false",
    "benchmark_performance_claim: false",
    "raw_content_in_output: false",
    "verdict: PASS",
    "source_sha256: a7a751066c48e829b3012a94f2b365febd0e6fb6db454a6d5f4ec01f9c55008a",
    "projected_record_count: 2060",
    "adapter_accepted_edge_count: 2703",
    "resolver_added_memory_used_edges: 327",
    "resolver_added_fallback_source_turn_edges: 30",
    "final_accepted_edge_count: 3060",
    "adapter_edge_candidate_count: 3060",
    "resolved_reference_count: 763",
    "residual_unresolved_count: 7",
    "source_turn_negative: 7",
    "accepted_projection_item_count: 5120",
    "final_accepted_edges_match_adapter_candidates: true",
    "memory_used_fully_resolved: true",
    "source_turn_indexing_fully_resolved: true",
    "residual_unresolved_only_negative_source_turn: true",
    "memory_rows_delta: 0",
    "memory_edges_delta: 0",
    "semantic_events_delta: 0",
    "realmem_real_runner_boundary_packet",
]

missing = [needle for needle in required if needle not in text]
if missing:
    raise SystemExit("Missing required RealMem gate report anchors: " + ", ".join(missing))

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
meaning_index = text.index("## Gate Meaning")
boundary_index = text.index("## Boundary")
next_step_index = text.index("## Next Step")
assert verdict_index < meaning_index < boundary_index < next_step_index

print("RealMem resolved projection gate report verification passed")
PY
