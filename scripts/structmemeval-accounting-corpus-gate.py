#!/usr/bin/env python3
"""Run the local StructMemEval accounting candidate corpus gate.

This is a local fixture gate, not a StructMemEval benchmark score. It consumes
the checked-in accounting candidate corpus, runs the deterministic accounting
normalizer in --review-summary mode for accepted candidates, verifies rejected
candidates fail, and emits a redacted PASS/FAIL packet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.structmemeval_accounting_corpus_gate.v0"
FIXTURE_SCHEMA = "agent_bridge.structmemeval_accounting_candidate_corpus.v0"
SUMMARY_SCHEMA = "agent_bridge.structmemeval_accounting_normalizer_review_summary.v0"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "scripts/eval/fixtures/structmemeval_accounting_candidate_corpus.json"
DEFAULT_NORMALIZER = ROOT / "scripts/structmemeval-accounting-normalizer.py"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_fixture(path: Path) -> dict[str, Any]:
    try:
        fixture = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - report parse failure to operator
        fail(f"failed to read fixture {path}: {exc}")
    if fixture.get("schema") != FIXTURE_SCHEMA:
        fail(f"unexpected fixture schema: {fixture.get('schema')!r}")
    return fixture


def create_store(path: Path) -> None:
    con = sqlite3.connect(path)
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


def run_review_summary(
    normalizer: Path,
    fixture: dict[str, Any],
    tmpdir: Path,
) -> tuple[dict[str, Any], str]:
    case_path = tmpdir / "accounting-candidate-case.json"
    store_db = tmpdir / "state.db"
    output_json = tmpdir / "review-summary.json"
    case_path.write_text(json.dumps(fixture["case"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    create_store(store_db)

    cmd = [
        sys.executable,
        str(normalizer),
        "--case",
        str(case_path),
        "--store-db",
        str(store_db),
        "--review-summary",
        "--output",
        str(output_json),
    ]
    for candidate in fixture["accepted_candidates"]:
        cmd.extend(["--answer", candidate["answer"]])
    subprocess.run(cmd, check=True)
    text = output_json.read_text(encoding="utf-8")
    packet = json.loads(text)
    if packet.get("schema") != SUMMARY_SCHEMA:
        fail(f"unexpected review summary schema: {packet.get('schema')!r}")
    return packet, text


def review_accepted(summary: dict[str, Any], fixture: dict[str, Any]) -> list[dict[str, Any]]:
    reviews = []
    candidates = summary["candidate_reviews"]
    accepted = fixture["accepted_candidates"]
    if len(candidates) != len(accepted):
        fail("candidate review count mismatch")
    for candidate, expected in zip(candidates, accepted, strict=True):
        checks = {
            "exact_reference_match": (
                candidate["exact_reference_match"] == expected["expected_exact_reference_match"]
            ),
            "matched_reference_variant_indices": (
                candidate["matched_reference_variant_indices"]
                == expected["expected_matched_reference_variant_indices"]
            ),
            "transaction_count": candidate["transaction_count"] == expected["expected_transaction_count"],
            "transactions": candidate["transactions"] == expected["expected_transactions"],
        }
        reviews.append(
            {
                "id": expected["id"],
                "class": expected["class"],
                "source_text_sha256": candidate["source_text_sha256"],
                "canonical_key_sha256": candidate["canonical_key_sha256"],
                "expected_exact_reference_match": expected["expected_exact_reference_match"],
                "actual_exact_reference_match": candidate["exact_reference_match"],
                "matched_reference_variant_indices": candidate["matched_reference_variant_indices"],
                "transaction_count": candidate["transaction_count"],
                "transactions": candidate["transactions"],
                "checks": checks,
                "passed": all(checks.values()),
            }
        )
    return reviews


def review_rejected(normalizer: Path, fixture: dict[str, Any], tmpdir: Path) -> list[dict[str, Any]]:
    case_path = tmpdir / "accounting-candidate-case.json"
    reviews = []
    for candidate in fixture["rejected_candidates"]:
        result = subprocess.run(
            [
                sys.executable,
                str(normalizer),
                "--case",
                str(case_path),
                "--answer",
                candidate["answer"],
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        regex_match = bool(re.search(candidate["expected_stderr_regex"], result.stderr))
        reviews.append(
            {
                "id": candidate["id"],
                "class": candidate["class"],
                "expected_rejection": True,
                "actual_rejected": result.returncode != 0,
                "stderr_sha256": hashlib.sha256(result.stderr.encode("utf-8")).hexdigest(),
                "expected_stderr_regex": candidate["expected_stderr_regex"],
                "regex_matched": regex_match,
                "passed": result.returncode != 0 and regex_match,
            }
        )
    return reviews


def no_write_summary(summary: dict[str, Any]) -> dict[str, Any]:
    proof = summary["no_write_invariant"]
    return {
        "checked": proof.get("checked"),
        "passed": proof.get("passed"),
        "memory_rows_delta": proof.get("memory_rows_delta"),
        "memory_edges_delta": proof.get("memory_edges_delta"),
        "semantic_events_delta": proof.get("semantic_events_delta"),
    }


def raw_strings(fixture: dict[str, Any]) -> list[str]:
    strings = []
    for message in fixture["case"]["sessions"][0]["messages"]:
        strings.append(message["content"])
    for query in fixture["case"]["queries"]:
        strings.append(query["question"])
        for reference in query["reference_answer"]:
            strings.append(reference["text"])
    for candidate in fixture["accepted_candidates"] + fixture["rejected_candidates"]:
        strings.append(candidate["answer"])
    return strings


def build_packet(fixture_path: Path, normalizer: Path) -> tuple[dict[str, Any], str]:
    fixture = load_fixture(fixture_path)
    with tempfile.TemporaryDirectory(prefix="ab-structmemeval-accounting-gate-") as tmp:
        tmpdir = Path(tmp)
        summary, summary_text = run_review_summary(normalizer, fixture, tmpdir)
        accepted_reviews = review_accepted(summary, fixture)
        rejected_reviews = review_rejected(normalizer, fixture, tmpdir)

    accepted_pass_count = sum(1 for item in accepted_reviews if item["passed"])
    rejected_pass_count = sum(1 for item in rejected_reviews if item["passed"])
    proof = no_write_summary(summary)
    verdict = (
        proof["passed"] is True
        and accepted_pass_count == len(accepted_reviews)
        and rejected_pass_count == len(rejected_reviews)
    )
    packet = {
        "schema": SCHEMA,
        "fixture_schema": fixture["schema"],
        "review_summary_schema": SUMMARY_SCHEMA,
        "normalizer_schema": summary["source_schema"],
        "scope": "local_accounting_candidate_corpus_only",
        "verdict": "PASS" if verdict else "FAIL",
        "benchmark_performance_claim": False,
        "structmemeval_official_runner_used": False,
        "network_required": False,
        "third_party_runtime_dependencies": False,
        "api_key_required": False,
        "writes_ab_store": False,
        "raw_content_in_output": False,
        "comparison_mode": summary["comparison_mode"],
        "fixture": {
            "path": str(fixture_path.relative_to(ROOT)) if fixture_path.is_relative_to(ROOT) else str(fixture_path),
            "sha256": hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
            "accepted_candidate_count": len(accepted_reviews),
            "rejected_candidate_count": len(rejected_reviews),
        },
        "summary": {
            "accepted_pass_count": accepted_pass_count,
            "rejected_pass_count": rejected_pass_count,
            "candidate_exact_match_count": summary["summary"]["candidate_exact_match_count"],
            "candidate_answer_count": summary["summary"]["candidate_answer_count"],
            "reference_variant_count": summary["summary"]["reference_variant_count"],
        },
        "no_write_invariant": proof,
        "accepted_reviews": accepted_reviews,
        "rejected_reviews": rejected_reviews,
    }
    return packet, summary_text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", default=str(DEFAULT_FIXTURE), help="Candidate corpus JSON fixture.")
    parser.add_argument("--normalizer", default=str(DEFAULT_NORMALIZER), help="Accounting normalizer script.")
    parser.add_argument("--output", help="Write gate packet JSON to this path.")
    args = parser.parse_args()

    fixture_path = Path(args.fixture)
    normalizer = Path(args.normalizer)
    packet, summary_text = build_packet(fixture_path, normalizer)
    output = json.dumps(packet, ensure_ascii=False, indent=2) + "\n"

    fixture = load_fixture(fixture_path)
    for value in raw_strings(fixture):
        if value in output or value in summary_text:
            fail("raw fixture string leaked into gate or review-summary output")

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0 if packet["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
