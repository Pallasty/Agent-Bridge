#!/usr/bin/env bash
# Offline verification for the StructMemEval accounting local corpus gate.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER="$ROOT_DIR/scripts/structmemeval-accounting-corpus-gate.py"
FIXTURE="$ROOT_DIR/scripts/eval/fixtures/structmemeval_accounting_candidate_corpus.json"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-structmemeval-accounting-gate-XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

output_json="$tmpdir/corpus-gate.json"
python3 "$HELPER" --fixture "$FIXTURE" --output "$output_json"

python3 - "$output_json" "$FIXTURE" <<'PY'
import json
import sys
from pathlib import Path

output_path = Path(sys.argv[1])
fixture_path = Path(sys.argv[2])
text = output_path.read_text(encoding="utf-8")
packet = json.loads(text)
fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

assert packet["schema"] == "agent_bridge.structmemeval_accounting_corpus_gate.v0"
assert packet["fixture_schema"] == "agent_bridge.structmemeval_accounting_candidate_corpus.v0"
assert packet["review_summary_schema"] == (
    "agent_bridge.structmemeval_accounting_normalizer_review_summary.v0"
)
assert packet["normalizer_schema"] == "agent_bridge.structmemeval_accounting_normalizer.v0"
assert packet["scope"] == "local_accounting_candidate_corpus_only"
assert packet["verdict"] == "PASS"
assert packet["benchmark_performance_claim"] is False
assert packet["structmemeval_official_runner_used"] is False
assert packet["network_required"] is False
assert packet["third_party_runtime_dependencies"] is False
assert packet["api_key_required"] is False
assert packet["writes_ab_store"] is False
assert packet["raw_content_in_output"] is False
assert packet["comparison_mode"] == "exact_canonical_transaction_set"

assert packet["fixture"]["accepted_candidate_count"] == 7
assert packet["fixture"]["rejected_candidate_count"] == 5
summary = packet["summary"]
assert summary["accepted_pass_count"] == 7
assert summary["rejected_pass_count"] == 5
assert summary["candidate_answer_count"] == 7
assert summary["candidate_exact_match_count"] == 5
assert summary["reference_variant_count"] == 3

proof = packet["no_write_invariant"]
assert proof == {
    "checked": True,
    "passed": True,
    "memory_rows_delta": 0,
    "memory_edges_delta": 0,
    "semantic_events_delta": 0,
}

accepted = packet["accepted_reviews"]
rejected = packet["rejected_reviews"]
assert len(accepted) == 7
assert len(rejected) == 5
assert all(item["passed"] is True for item in accepted)
assert all(item["passed"] is True for item in rejected)
assert sum(1 for item in accepted if item["actual_exact_reference_match"]) == 5
assert {item["class"] for item in rejected} == {
    "ambiguous",
    "grammar_limit",
    "amount_limit",
    "semantic_limit",
}

for message in fixture["case"]["sessions"][0]["messages"]:
    assert message["content"] not in text
for query in fixture["case"]["queries"]:
    assert query["question"] not in text
    for reference in query["reference_answer"]:
        assert reference["text"] not in text
for candidate in fixture["accepted_candidates"] + fixture["rejected_candidates"]:
    assert candidate["answer"] not in text
for disallowed in [
    '"content"',
    '"question"',
    '"reference_answer"',
    '"text"',
    '"store_db"',
    '"before"',
    '"after"',
    "benchmark performance",
    "StructMemEval benchmark performance",
]:
    assert disallowed not in text

print("StructMemEval accounting local corpus gate verification passed")
PY
