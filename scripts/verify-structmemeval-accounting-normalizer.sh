#!/usr/bin/env bash
# Offline verification for the StructMemEval accounting answer normalizer.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER="$ROOT_DIR/scripts/structmemeval-accounting-normalizer.py"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-structmemeval-accounting-XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

case_json="$tmpdir/accounting.json"
store_db="$tmpdir/state.db"
output_json="$tmpdir/output.json"

cat > "$case_json" <<'JSON'
{
  "case_id": "accounting_unit_1",
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
        {"text": "Settlement: Charlie -> Bob : 218.33 EUR, Alice -> Bob : 24.83 EUR"},
        {"text": "Charlie pays 153.67 EUR to Bob; Alice pays 28.67 EUR to Bob"},
        {"text": "Alice pays Bob 141.83 EUR and Alice pays Charlie 95.33 EUR"}
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
  --case "$case_json" \
  --store-db "$store_db" \
  --answer "Alice pays 28.67 EUR to Bob; Charlie pays 153.67 EUR to Bob" \
  --answer "Bob receives 218.33 EUR from Charlie, Bob receives 24.83 EUR from Alice" \
  --answer "Alice owes Bob 1.00 EUR" \
  --output "$output_json"

python3 - "$output_json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    packet = json.load(f)

assert packet["schema"] == "agent_bridge.structmemeval_accounting_normalizer.v0"
assert packet["family"] == "accounting"
assert packet["official_runner_import_allowed"] is False
assert packet["third_party_runtime_dependencies"] is False
assert packet["api_key_required"] is False
assert packet["private_memory_export_allowed"] is False
assert packet["writes_ab_store"] is False
assert packet["raw_content_in_output"] is False
assert packet["comparison_mode"] == "exact_canonical_transaction_set"
assert set(packet["grammar"]) == {
    "arrow",
    "pays_amount_to",
    "pays_payee_amount",
    "owes",
    "receives_from",
}

case = packet["case"]
assert case["case_id"] == "accounting_unit_1"
assert case["source_mode"] == "file"
assert case["query_count"] == 1
assert case["reference_variant_count"] == 3

summary = packet["summary"]
assert summary["reference_variant_count"] == 3
assert summary["reference_transaction_count_min"] == 2
assert summary["reference_transaction_count_max"] == 2
assert summary["candidate_answer_count"] == 3
assert summary["candidate_exact_match_count"] == 2

variants = packet["reference_variants"]
assert len(variants) == 3
assert variants[0]["transactions"] == [
    {
        "payer": "Alice",
        "payee": "Bob",
        "currency": "EUR",
        "amount_cents": 2483,
        "amount": "24.83",
    },
    {
        "payer": "Charlie",
        "payee": "Bob",
        "currency": "EUR",
        "amount_cents": 21833,
        "amount": "218.33",
    },
]
assert variants[1]["transactions"] == [
    {
        "payer": "Alice",
        "payee": "Bob",
        "currency": "EUR",
        "amount_cents": 2867,
        "amount": "28.67",
    },
    {
        "payer": "Charlie",
        "payee": "Bob",
        "currency": "EUR",
        "amount_cents": 15367,
        "amount": "153.67",
    },
]
assert variants[2]["transactions"] == [
    {
        "payer": "Alice",
        "payee": "Bob",
        "currency": "EUR",
        "amount_cents": 14183,
        "amount": "141.83",
    },
    {
        "payer": "Alice",
        "payee": "Charlie",
        "currency": "EUR",
        "amount_cents": 9533,
        "amount": "95.33",
    },
]

candidates = packet["candidate_answers"]
assert candidates[0]["exact_reference_match"] is True
assert candidates[0]["matched_reference_variant_indices"] == [2]
assert candidates[1]["exact_reference_match"] is True
assert candidates[1]["matched_reference_variant_indices"] == [1]
assert candidates[2]["exact_reference_match"] is False
assert candidates[2]["matched_reference_variant_indices"] == []

proof = packet["no_write_invariant"]
assert proof["checked"] is True
assert proof["passed"] is True
assert proof["memory_rows_delta"] == 0
assert proof["memory_edges_delta"] == 0
assert proof["semantic_events_delta"] == 0

text = json.dumps(packet)
for disallowed_key in ['"content"', '"question"', '"reference_answer"', '"text"']:
    assert disallowed_key not in text

print("StructMemEval accounting normalizer verification passed")
PY

if python3 "$HELPER" --case "$case_json" --answer "Alice paid something to Bob" \
  > "$tmpdir/stdout-bad" 2> "$tmpdir/stderr-bad"; then
  echo "expected ambiguous candidate answer to fail" >&2
  exit 1
fi
grep -q "supported settlement transaction\\|unsupported leftover text" "$tmpdir/stderr-bad"
