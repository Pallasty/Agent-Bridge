#!/usr/bin/env python3
"""Aggregate-only R2 audit of episode membership recoverability."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Any


SCHEMA = "agent_bridge.free_recall_strategy_r2_episode_audit.v0"
FIXTURE = "synthesis_queries.json"
FIXTURE_SHA256 = "b4eb4bc7b977c4df3773478eed68c763331a2e161088e4f27485cc2bc04b5522"
PROVENANCE_PREFIXES = {
    "batch",
    "source",
    "arc",
    "zone",
    "distill_prompt",
    "method",
    "verify",
    "verdict",
    "proposes",
    "derived",
    "deploy",
}


class AuditError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_cases(fixture: Path) -> list[dict[str, Any]]:
    if sha256_file(fixture) != FIXTURE_SHA256:
        raise AuditError("synthesis fixture hash drift")
    value = json.loads(fixture.read_text(encoding="utf-8"))
    cases = value.get("queries")
    if not isinstance(cases, list) or len(cases) != 13:
        raise AuditError("synthesis fixture shape drift")
    return cases


def read_only_backup(source: Path, destination: Path) -> tuple[int, int]:
    source_db = sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
    before = source_db.total_changes
    try:
        source_db.execute("PRAGMA query_only=ON")
        destination_db = sqlite3.connect(destination)
        try:
            source_db.backup(destination_db)
        finally:
            destination_db.close()
    finally:
        after = source_db.total_changes
        source_db.close()
    return before, after


def pair(left: str, right: str) -> tuple[str, str]:
    return (left, right) if left < right else (right, left)


def load_snapshot(snapshot: Path, universe: set[str]) -> tuple[dict[str, Any], set[tuple[str, str]]]:
    db = sqlite3.connect(snapshot.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        placeholders = ",".join("?" for _ in universe)
        rows = db.execute(
            "SELECT key, tags, related_keys, scope, created_at, status FROM memories "
            f"WHERE key IN ({placeholders}) ORDER BY key",
            tuple(sorted(universe)),
        ).fetchall()
        records = {
            key: {
                "tags": set(json.loads(tags or "[]")),
                "related": set(json.loads(related or "[]")),
                "scope": scope,
                "created_at": created_at,
                "status": status,
            }
            for key, tags, related, scope, created_at, status in rows
        }
        if set(records) != universe or any(row["status"] != "active" for row in records.values()):
            raise AuditError("CORPUS_DRIFT_BLOCKED")
        edge_rows = db.execute(
            "SELECT from_key, to_key FROM memory_edges WHERE edge_type != 'coactivation'"
        ).fetchall()
        edges = {
            pair(left, right)
            for left, right in edge_rows
            if left in universe and right in universe and left != right
        }
    finally:
        db.close()
    return records, edges


def tag_prefix(tag: str) -> str:
    return tag.split(":", 1)[0] if ":" in tag else "<bare>"


def predictions(records: dict[str, Any], edges: set[tuple[str, str]]) -> dict[str, set[tuple[str, str]]]:
    channels = {
        name: set()
        for name in (
            "all_exact_tags",
            "provenance_tags",
            "related_keys",
            "non_coactivation_edge",
            "time_5m",
            "time_30m",
            "time_2h",
            "provenance_or_structure",
            "all_metadata_union",
            "all_pairs_positive",
        )
    }
    keys = sorted(records)
    for left, right in itertools.combinations(keys, 2):
        identity = (left, right)
        a, b = records[left], records[right]
        shared_tags = a["tags"] & b["tags"]
        if shared_tags:
            channels["all_exact_tags"].add(identity)
        if any(tag_prefix(tag) in PROVENANCE_PREFIXES for tag in shared_tags):
            channels["provenance_tags"].add(identity)
        if right in a["related"] or left in b["related"]:
            channels["related_keys"].add(identity)
        if identity in edges:
            channels["non_coactivation_edge"].add(identity)
        if a["scope"] == b["scope"]:
            distance = abs(int(a["created_at"]) - int(b["created_at"]))
            if distance <= 300:
                channels["time_5m"].add(identity)
            if distance <= 1800:
                channels["time_30m"].add(identity)
            if distance <= 7200:
                channels["time_2h"].add(identity)
        channels["all_pairs_positive"].add(identity)
    channels["provenance_or_structure"] = (
        channels["provenance_tags"]
        | channels["related_keys"]
        | channels["non_coactivation_edge"]
    )
    channels["all_metadata_union"] = (
        channels["all_exact_tags"]
        | channels["related_keys"]
        | channels["non_coactivation_edge"]
        | channels["time_30m"]
    )
    return channels


def score(predicted: set[tuple[str, str]], positive: set[tuple[str, str]]) -> dict[str, Any]:
    tp = len(predicted & positive)
    fp = len(predicted - positive)
    fn = len(positive - predicted)
    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(positive) if positive else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    eligible = len(predicted) >= 5
    return {
        "predicted_pairs": len(predicted),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "coverage_eligible": eligible,
        "passes": eligible and precision >= 0.70 and recall >= 0.50 and f1 >= 0.58,
    }


def evaluate(cases: list[dict[str, Any]], records: dict[str, Any], edges: set[tuple[str, str]]) -> dict[str, Any]:
    positive: set[tuple[str, str]] = set()
    for case in cases:
        gold = sorted(set(case["gold_set"]))
        positive.update(itertools.combinations(gold, 2))
    all_pairs = set(itertools.combinations(sorted(records), 2))
    if not positive <= all_pairs:
        raise AuditError("positive pair outside active universe")
    channel_scores = {
        name: score(rows, positive) for name, rows in predictions(records, edges).items()
    }
    return {
        "universe_keys": len(records),
        "all_pairs": len(all_pairs),
        "positive_pairs": len(positive),
        "negative_pairs": len(all_pairs - positive),
        "positive_prevalence": round(len(positive) / len(all_pairs), 6),
        "channels": channel_scores,
        "recoverability_gate": any(
            row["passes"]
            for name, row in channel_scores.items()
            if name != "all_pairs_positive"
        ),
    }


def run(source_db: Path, fixture: Path) -> dict[str, Any]:
    cases = load_cases(fixture)
    universe = {key for case in cases for key in case["gold_set"]}
    with tempfile.TemporaryDirectory(prefix="ab-free-recall-r2-") as temp:
        snapshot = Path(temp) / "state.snapshot.db"
        source_before, source_after = read_only_backup(source_db, snapshot)
        snapshot_before = sha256_file(snapshot)
        records, edges = load_snapshot(snapshot, universe)
        forward = evaluate(cases, records, edges)
        reverse = evaluate(list(reversed(cases)), records, edges)
        stripped = evaluate(
            [{"gold_set": case["gold_set"]} for case in cases], records, edges
        )
        if forward != reverse or forward != stripped:
            raise AuditError("LEAKAGE_FALSIFIER_BLOCKED")
        snapshot_after = sha256_file(snapshot)
        if snapshot_before != snapshot_after:
            raise AuditError("read-only snapshot changed")
    return {
        "schema": SCHEMA,
        "status": "AUDIT_COMPLETE_NO_RETRIEVAL_AUTHORITY",
        "fixture_sha256": FIXTURE_SHA256,
        "read_only_source": True,
        "source_total_changes_before": source_before,
        "source_total_changes_after": source_after,
        "snapshot_sha256_before": snapshot_before,
        "snapshot_sha256_after": snapshot_after,
        "case_order_falsifier": "PASS",
        "query_and_notes_stripped_falsifier": "PASS",
        "result": forward,
    }


def selftest() -> None:
    records = {
        "a": {"tags": {"batch:x"}, "related": set(), "scope": "s", "created_at": 0},
        "b": {"tags": {"batch:x"}, "related": set(), "scope": "s", "created_at": 100},
        "c": {"tags": {"batch:y"}, "related": set(), "scope": "s", "created_at": 10_000},
    }
    result = evaluate([{"gold_set": ["a", "b"]}], records, set())
    row = result["channels"]["provenance_tags"]
    if row["true_positive"] != 1 or row["false_positive"] != 0:
        raise AssertionError("provenance scoring drift")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--source-db", type=Path)
    parser.add_argument("--fixture", type=Path, default=Path(__file__).parent / "fixtures" / FIXTURE)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.selftest:
        selftest()
        print("selftest: PASS")
        if args.source_db is None:
            return 0
    if args.source_db is None or args.out is None:
        parser.error("--source-db and --out are required")
    report = run(args.source_db.resolve(), args.fixture.resolve())
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["result"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
