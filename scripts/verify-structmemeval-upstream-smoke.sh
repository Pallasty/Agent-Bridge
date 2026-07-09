#!/usr/bin/env bash
# Network smoke test for the pinned StructMemEval default samples.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER="$ROOT_DIR/scripts/structmemeval-adapter-contract.py"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-structmemeval-upstream-XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

store_db="$tmpdir/state.db"
output_json="$tmpdir/upstream-smoke.json"

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

python3 "$HELPER" --store-db "$store_db" --output "$output_json"

python3 - "$output_json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
packet = json.loads(text)

assert packet["schema"] == "agent_bridge.structmemeval_adapter_contract_impl.v0"
assert packet["source_head"] == "64d2c9b242deb394e3ef94a318868a55261e141b"
assert packet["official_runner_import_allowed"] is False
assert packet["third_party_runtime_dependencies"] is False
assert packet["api_key_required"] is False
assert packet["private_memory_export_allowed"] is False
assert packet["writes_ab_store"] is False
assert packet["raw_content_in_output"] is False

summary = packet["summary"]
assert summary["input_case_count"] == 3
assert summary["session_count"] == 5
assert summary["turn_count"] == 90
assert summary["query_count"] == 31
assert summary["temporary_record_count"] == 126
assert summary["temporary_edge_count"] == 123
assert summary["reference_answer_shapes"] == {"array": 1, "object": 30}

proof = packet["no_write_invariant"]
assert proof["checked"] is True
assert proof["passed"] is True
assert proof["memory_rows_delta"] == 0
assert proof["memory_edges_delta"] == 0
assert proof["semantic_events_delta"] == 0

expected = {
    "tree_based": {
        "case_id": "graph_0_trimmed_10_with_path_1",
        "sha256": "644723537360e49395afbf879dd30c7ee31158e46c8b7bb23b83214089ece593",
        "bytes": 15694,
        "session_count": 1,
        "turn_count": 10,
        "query_count": 29,
        "temporary_record_count": 40,
        "temporary_edge_count": 39,
        "reference_answer_shapes": {"object": 29},
    },
    "state_machine_location": {
        "case_id": "static_001",
        "sha256": "de30dbf512fa9fbb8b6c449f98e0cad06382fd7b5ecd0d1a8a310f21b3ed0ece",
        "bytes": 4172,
        "session_count": 3,
        "turn_count": 30,
        "query_count": 1,
        "temporary_record_count": 34,
        "temporary_edge_count": 33,
        "reference_answer_shapes": {"object": 1},
    },
    "accounting": {
        "case_id": "accounting_10__1",
        "sha256": "94cc1e965c43f3a2acb56a8e98306161174b77d34d548f486b6d9f8766d4adf9",
        "bytes": 5546,
        "session_count": 1,
        "turn_count": 50,
        "query_count": 1,
        "temporary_record_count": 52,
        "temporary_edge_count": 51,
        "reference_answer_shapes": {"array": 1},
    },
}

cases = {case["family"]: case for case in packet["cases"]}
assert set(cases) == set(expected)
for family, checks in expected.items():
    case = cases[family]
    assert case["source_mode"] == "url"
    assert case["sample_edge_types"] == ["derived_from", "relates"]
    assert case["sample_record_keys"]
    for field, value in checks.items():
        assert case[field] == value

for disallowed_key in ['"content"', '"question"', '"reference_answer"', '"expected_answer"']:
    assert disallowed_key not in text

print("StructMemEval pinned upstream smoke passed")
PY
