#!/usr/bin/env bash
# Network smoke test for the pinned StructMemEval accounting normalizer sample.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER="$ROOT_DIR/scripts/structmemeval-accounting-normalizer.py"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-structmemeval-accounting-upstream-XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

store_db="$tmpdir/state.db"
output_json="$tmpdir/accounting-upstream-smoke.json"

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

assert packet["schema"] == "agent_bridge.structmemeval_accounting_normalizer.v0"
assert packet["source_head"] == "64d2c9b242deb394e3ef94a318868a55261e141b"
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
assert case["case_id"] == "accounting_10__1"
assert case["source_mode"] == "url"
assert case["sha256"] == "94cc1e965c43f3a2acb56a8e98306161174b77d34d548f486b6d9f8766d4adf9"
assert case["bytes"] == 5546
assert case["query_count"] == 1
assert case["reference_variant_count"] == 3

summary = packet["summary"]
assert summary == {
    "reference_variant_count": 3,
    "reference_transaction_count_min": 2,
    "reference_transaction_count_max": 2,
    "candidate_answer_count": 0,
    "candidate_exact_match_count": 0,
}

expected_variants = [
    {
        "variant_index": 1,
        "source_text_sha256": "2b179397d04d0ef059b8f313b795e125e45295213432c5a6f8a983b81cc7a785",
        "canonical_key_sha256": "f855f8eeb2cbd4691a4d7b16992bb29b6f41c38c0e5502e97a3cadca4844a2e5",
        "transactions": [
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
        ],
    },
    {
        "variant_index": 2,
        "source_text_sha256": "ccef00787906c0697588c0b99ca13be80c08914ddb536d3d143f2477cda27fef",
        "canonical_key_sha256": "b7340aa75181dc40d7947d7d965c23041c511008f05e74c5876a89ebb469afce",
        "transactions": [
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
        ],
    },
    {
        "variant_index": 3,
        "source_text_sha256": "af57899f6adf3524373f296af383c685e896da4f3829e85191e65ce67463a40b",
        "canonical_key_sha256": "305822d893ce37cce6f4862ad2e2c1f5086008a1c23e6c9dec34946daa9d684b",
        "transactions": [
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
        ],
    },
]

variants = packet["reference_variants"]
assert len(variants) == len(expected_variants)
for actual, expected in zip(variants, expected_variants, strict=True):
    assert actual["query_index"] == 1
    assert actual["variant_index"] == expected["variant_index"]
    assert actual["source_text_sha256"] == expected["source_text_sha256"]
    assert actual["canonical_key_sha256"] == expected["canonical_key_sha256"]
    assert actual["matched_patterns"] == ["arrow"]
    assert actual["transaction_count"] == 2
    assert actual["transactions"] == expected["transactions"]

assert packet["candidate_answers"] == []

proof = packet["no_write_invariant"]
assert proof["checked"] is True
assert proof["passed"] is True
assert proof["memory_rows_delta"] == 0
assert proof["memory_edges_delta"] == 0
assert proof["semantic_events_delta"] == 0

for disallowed_key in [
    '"content"',
    '"question"',
    '"reference_answer"',
    '"expected_answer"',
    '"stated_fact"',
    '"text":',
]:
    assert disallowed_key not in text

print("StructMemEval accounting upstream normalizer smoke passed")
PY
