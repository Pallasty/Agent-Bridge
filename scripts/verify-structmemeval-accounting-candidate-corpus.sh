#!/usr/bin/env bash
# Offline verification for the StructMemEval accounting candidate-answer corpus.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HELPER="$ROOT_DIR/scripts/structmemeval-accounting-normalizer.py"
FIXTURE="$ROOT_DIR/scripts/eval/fixtures/structmemeval_accounting_candidate_corpus.json"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ab-structmemeval-accounting-corpus-XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT

python3 - "$HELPER" "$FIXTURE" "$tmpdir" <<'PY'
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

helper = Path(sys.argv[1])
fixture_path = Path(sys.argv[2])
tmpdir = Path(sys.argv[3])

fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
assert fixture["schema"] == "agent_bridge.structmemeval_accounting_candidate_corpus.v0"

case_path = tmpdir / "accounting-candidate-case.json"
store_db = tmpdir / "state.db"
output_json = tmpdir / "accepted-output.json"
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

accepted = fixture["accepted_candidates"]
cmd = [
    sys.executable,
    str(helper),
    "--case",
    str(case_path),
    "--store-db",
    str(store_db),
    "--output",
    str(output_json),
]
for candidate in accepted:
    cmd.extend(["--answer", candidate["answer"]])
subprocess.run(cmd, check=True)

output_text = output_json.read_text(encoding="utf-8")
packet = json.loads(output_text)
assert packet["schema"] == "agent_bridge.structmemeval_accounting_normalizer.v0"
assert packet["family"] == "accounting"
assert packet["official_runner_import_allowed"] is False
assert packet["third_party_runtime_dependencies"] is False
assert packet["api_key_required"] is False
assert packet["private_memory_export_allowed"] is False
assert packet["writes_ab_store"] is False
assert packet["raw_content_in_output"] is False
assert packet["comparison_mode"] == "exact_canonical_transaction_set"

summary = packet["summary"]
expected_exact = sum(1 for candidate in accepted if candidate["expected_exact_reference_match"])
assert summary["reference_variant_count"] == 3
assert summary["reference_transaction_count_min"] == 2
assert summary["reference_transaction_count_max"] == 2
assert summary["candidate_answer_count"] == len(accepted)
assert summary["candidate_exact_match_count"] == expected_exact

proof = packet["no_write_invariant"]
assert proof["checked"] is True
assert proof["passed"] is True
assert proof["memory_rows_delta"] == 0
assert proof["memory_edges_delta"] == 0
assert proof["semantic_events_delta"] == 0

actual_candidates = packet["candidate_answers"]
assert len(actual_candidates) == len(accepted)
for actual, expected in zip(actual_candidates, accepted, strict=True):
    assert actual["exact_reference_match"] == expected["expected_exact_reference_match"]
    assert (
        actual["matched_reference_variant_indices"]
        == expected["expected_matched_reference_variant_indices"]
    )
    assert actual["transaction_count"] == expected["expected_transaction_count"]
    assert actual["transactions"] == expected["expected_transactions"]
    assert expected["answer"] not in output_text

for reference in fixture["case"]["queries"][0]["reference_answer"]:
    assert reference["text"] not in output_text

for disallowed_key in ['"content"', '"question"', '"reference_answer"', '"text"']:
    assert disallowed_key not in output_text

rejected = fixture["rejected_candidates"]
for candidate in rejected:
    bad_output = tmpdir / f"{candidate['id']}.json"
    result = subprocess.run(
        [
            sys.executable,
            str(helper),
            "--case",
            str(case_path),
            "--answer",
            candidate["answer"],
            "--output",
            str(bad_output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        raise AssertionError(f"{candidate['id']} unexpectedly passed")
    assert re.search(candidate["expected_stderr_regex"], result.stderr), (
        candidate["id"],
        result.stderr,
    )
    if bad_output.exists():
        bad_text = bad_output.read_text(encoding="utf-8")
        assert candidate["answer"] not in bad_text

print(
    "StructMemEval accounting candidate corpus verification passed "
    f"({len(accepted)} accepted, {len(rejected)} rejected)"
)
PY
