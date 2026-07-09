#!/usr/bin/env bash
# Offline verification for the StructMemEval accounting review-summary mode.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER="$ROOT_DIR/scripts/structmemeval-accounting-normalizer.py"
FIXTURE="$ROOT_DIR/scripts/eval/fixtures/structmemeval_accounting_candidate_corpus.json"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-structmemeval-accounting-summary-XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

python3 - "$HELPER" "$FIXTURE" "$tmpdir" <<'PY'
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

helper = Path(sys.argv[1])
fixture_path = Path(sys.argv[2])
tmpdir = Path(sys.argv[3])

fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
case_path = tmpdir / "accounting-candidate-case.json"
store_db = tmpdir / "state.db"
output_json = tmpdir / "review-summary.json"
case_path.write_text(json.dumps(fixture["case"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

con = sqlite3.connect(store_db)
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

cmd = [
    sys.executable,
    str(helper),
    "--case",
    str(case_path),
    "--store-db",
    str(store_db),
    "--review-summary",
    "--output",
    str(output_json),
]
for candidate in fixture["accepted_candidates"][:4]:
    cmd.extend(["--answer", candidate["answer"]])
subprocess.run(cmd, check=True)

text = output_json.read_text(encoding="utf-8")
packet = json.loads(text)

assert packet["schema"] == "agent_bridge.structmemeval_accounting_normalizer_review_summary.v0"
assert packet["source_schema"] == "agent_bridge.structmemeval_accounting_normalizer.v0"
assert packet["family"] == "accounting"
assert packet["official_runner_import_allowed"] is False
assert packet["third_party_runtime_dependencies"] is False
assert packet["api_key_required"] is False
assert packet["private_memory_export_allowed"] is False
assert packet["writes_ab_store"] is False
assert packet["raw_content_in_output"] is False
assert packet["comparison_mode"] == "exact_canonical_transaction_set"

case = packet["case"]
assert set(case) == {
    "case_id",
    "source_mode",
    "sha256",
    "bytes",
    "query_count",
    "reference_variant_count",
}
assert case["case_id"] == "accounting_candidate_corpus_unit_1"
assert case["source_mode"] == "file"
assert case["query_count"] == 1
assert case["reference_variant_count"] == 3

summary = packet["summary"]
assert summary["reference_variant_count"] == 3
assert summary["reference_transaction_count_min"] == 2
assert summary["reference_transaction_count_max"] == 2
assert summary["candidate_answer_count"] == 4
assert summary["candidate_exact_match_count"] == 4

assert len(packet["reference_variants"]) == 3
assert len(packet["candidate_reviews"]) == 4
for variant in packet["reference_variants"]:
    assert "transactions" in variant
    assert "canonical_key_sha256" in variant
    assert "source_text_sha256" in variant
    assert "source" not in variant
for candidate in packet["candidate_reviews"]:
    assert candidate["exact_reference_match"] is True
    assert candidate["matched_reference_variant_indices"]
    assert "transactions" in candidate
    assert "canonical_key_sha256" in candidate
    assert "source" not in candidate

proof = packet["no_write_invariant"]
assert proof == {
    "checked": True,
    "passed": True,
    "memory_rows_delta": 0,
    "memory_edges_delta": 0,
    "semantic_events_delta": 0,
}

for candidate in fixture["accepted_candidates"][:4]:
    assert candidate["answer"] not in text
for reference in fixture["case"]["queries"][0]["reference_answer"]:
    assert reference["text"] not in text
for disallowed_key in [
    '"content"',
    '"question"',
    '"reference_answer"',
    '"text"',
    '"source":',
    '"before"',
    '"after"',
    '"store_db"',
]:
    assert disallowed_key not in text

print("StructMemEval accounting review summary verification passed")
PY
