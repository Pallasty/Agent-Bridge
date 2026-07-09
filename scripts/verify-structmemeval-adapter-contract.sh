#!/usr/bin/env bash
# Offline verification for the StructMemEval no-write adapter contract helper.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER="$ROOT_DIR/scripts/structmemeval-adapter-contract.py"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-structmemeval-contract-XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

tree_case="$tmpdir/tree.json"
state_case="$tmpdir/state.json"
accounting_case="$tmpdir/accounting.json"
store_db="$tmpdir/state.db"
output_json="$tmpdir/output.json"

cat > "$tree_case" <<'JSON'
{
  "case_id": "graph_0_trimmed_10_with_path_1",
  "sessions": [
    {
      "session_id": "session_01",
      "topic": "Small company relations",
      "messages": [
        {"role": "user", "content": "Johnny Fisher works with Christopher Peterson."},
        {"role": "user", "content": "Christopher Peterson is a colleague of Kathleen Herrera."},
        {"role": "user", "content": "Kathleen Herrera works with Linda Brooks."}
      ]
    }
  ],
  "queries": [
    {
      "question": "Are Johnny Fisher and Linda Brooks related through colleagues?",
      "reference_answer": {"text": "Yes, indirectly."}
    },
    {
      "question": "Who links Johnny Fisher to Kathleen Herrera?",
      "reference_answer": {"text": "Christopher Peterson."}
    }
  ]
}
JSON

cat > "$state_case" <<'JSON'
{
  "case_id": "static_001",
  "sessions": [
    {
      "session_id": "session_01",
      "topic": "User's life in Lisbon",
      "messages": [
        {"role": "user", "content": "I live in Lisbon, Alfama."},
        {"role": "assistant", "content": "How do you like living there?"}
      ]
    },
    {
      "session_id": "session_02",
      "topic": "Morning routine",
      "messages": [
        {"role": "user", "content": "I have a pastel de nata every morning."},
        {"role": "assistant", "content": "That sounds delicious."}
      ]
    }
  ],
  "queries": [
    {
      "question": "What do you have every morning?",
      "reference_answer": {"text": "A pastel de nata."}
    }
  ]
}
JSON

cat > "$accounting_case" <<'JSON'
{
  "case_id": "accounting_10_1",
  "sessions": [
    {
      "session_id": "session_01",
      "topic": "",
      "messages": [
        {"role": "user", "content": "Alice: Paid EUR 30 for dinner - split among all"},
        {"role": "user", "content": "Bob: Paid EUR 12 for taxi - split with Alice"},
        {"role": "user", "content": "Charlie: Refund EUR 3 each for all"}
      ]
    }
  ],
  "queries": [
    {
      "question": "Calculate settlement.",
      "reference_answer": [
        {"text": "Charlie pays Bob 1 EUR"},
        {"text": "Alice pays Bob 2 EUR"}
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
  --case "tree_based=$tree_case" \
  --case "state_machine_location=$state_case" \
  --case "accounting=$accounting_case" \
  --store-db "$store_db" \
  --output "$output_json"

python3 - "$output_json" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as f:
    packet = json.load(f)

assert packet["schema"] == "agent_bridge.structmemeval_adapter_contract_impl.v0"
assert packet["official_runner_import_allowed"] is False
assert packet["third_party_runtime_dependencies"] is False
assert packet["api_key_required"] is False
assert packet["private_memory_export_allowed"] is False
assert packet["writes_ab_store"] is False
assert packet["raw_content_in_output"] is False

summary = packet["summary"]
assert summary["input_case_count"] == 3
assert summary["session_count"] == 4
assert summary["turn_count"] == 10
assert summary["query_count"] == 4
assert summary["temporary_record_count"] == 18
assert summary["temporary_edge_count"] == 15
assert summary["reference_answer_shapes"] == {"array": 1, "object": 3}

proof = packet["no_write_invariant"]
assert proof["checked"] is True
assert proof["passed"] is True
assert proof["memory_rows_delta"] == 0
assert proof["memory_edges_delta"] == 0
assert proof["semantic_events_delta"] == 0

families = {case["family"] for case in packet["cases"]}
assert families == {"tree_based", "state_machine_location", "accounting"}
for case in packet["cases"]:
    assert case["sha256"]
    assert case["sample_record_keys"]
    assert "derived_from" in case["sample_edge_types"]

print("StructMemEval adapter contract verification passed")
PY

if python3 "$HELPER" --case "bad=$tmpdir/missing.json" --output "$tmpdir/bad.json" \
  > "$tmpdir/stdout-bad" 2> "$tmpdir/stderr-bad"; then
  echo "expected missing fixture to fail" >&2
  exit 1
fi
grep -q "case file not found" "$tmpdir/stderr-bad"
