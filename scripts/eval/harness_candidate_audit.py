"""Read-only audit of frozen, paired harness trials."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any


MODULES = {"agent_loop", "observation", "tools", "context_mgmt", "completion_detection"}
ARMS = {"baseline", "candidate"}
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
REVISION = re.compile(r"[0-9a-f]{40}\Z")


def _digest(value: object) -> bool:
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def _distinct_ids(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and item.strip() for item in value)
        and len(set(value)) == len(value)
    )


def evaluate(packet: dict[str, Any]) -> dict[str, Any]:
    """Audit a caller-supplied packet without executing tasks or promoting a candidate.

    This checks record consistency. It cannot authenticate a claimed verifier or
    establish that either run actually occurred.
    """
    reasons: set[str] = set()
    if packet.get("schema_version") != 1 or not isinstance(packet.get("trial_id"), str) or not packet["trial_id"].strip():
        reasons.add("invalid_header")
    module = packet.get("candidate_module")
    if not isinstance(module, str) or module not in MODULES:
        reasons.add("invalid_module")
    if any(
        not isinstance(packet.get(name), str) or REVISION.fullmatch(packet[name]) is None
        for name in ("baseline_revision", "candidate_revision")
    ):
        reasons.add("invalid_revision")
    elif packet["baseline_revision"] == packet["candidate_revision"]:
        reasons.add("unchanged_revision")
    exploration = packet.get("exploration_task_ids")
    evaluation = packet.get("evaluation_task_ids")
    if not _distinct_ids(exploration) or not _distinct_ids(evaluation):
        reasons.add("invalid_task_manifest")
        exploration_ids: set[str] = set()
        evaluation_ids: set[str] = set()
    else:
        exploration_ids = set(exploration)
        evaluation_ids = set(evaluation)
    if exploration_ids & evaluation_ids:
        reasons.add("task_overlap")

    runs = packet.get("runs")
    if not isinstance(runs, list):
        runs = []
        reasons.add("invalid_runs")
    pairs: dict[str, dict[str, dict[str, Any]]] = {}
    memory_by_arm: dict[str, set[str]] = {arm: set() for arm in ARMS}
    for run in runs:
        if not isinstance(run, dict):
            reasons.add("invalid_run")
            continue
        task_id, arm = run.get("task_id"), run.get("arm")
        if not isinstance(task_id, str) or task_id not in evaluation_ids or not isinstance(arm, str) or arm not in ARMS:
            reasons.add("unexpected_run")
            continue
        arms = pairs.setdefault(task_id, {})
        if arm in arms:
            reasons.add("duplicate_run")
            continue
        arms[arm] = run
        outcome = run.get("outcome")
        if not isinstance(outcome, str) or outcome not in {"pass", "fail"}:
            reasons.add("unresolved_outcome")
        if run.get("verifier_kind") != "independent":
            reasons.add("non_independent_verifier")
        if not _digest(run.get("evidence_sha256")):
            reasons.add("missing_evidence")
        if run.get("score_visible_to_learning") is not False:
            reasons.add("score_leakage")
        if not _digest(run.get("memory_sha256")):
            reasons.add("invalid_memory_digest")
        else:
            memory_by_arm[arm].add(run["memory_sha256"])
        if not isinstance(run.get("model"), str) or not run["model"].strip():
            reasons.add("invalid_model")
        if type(run.get("budget")) is not int or run["budget"] <= 0:
            reasons.add("invalid_budget")

    if set(pairs) != evaluation_ids or any(set(arms) != ARMS for arms in pairs.values()):
        reasons.add("incomplete_pair")
    if any(len(hashes) != 1 for hashes in memory_by_arm.values()):
        reasons.add("memory_drift")
    for arms in pairs.values():
        if set(arms) != ARMS:
            continue
        baseline, candidate = arms["baseline"], arms["candidate"]
        if baseline.get("model") != candidate.get("model"):
            reasons.add("model_mismatch")
        if baseline.get("budget") != candidate.get("budget"):
            reasons.add("budget_mismatch")

    valid_pairs = [arms for arms in pairs.values() if set(arms) == ARMS]
    improvements = sum(
        arms["baseline"].get("outcome") == "fail" and arms["candidate"].get("outcome") == "pass"
        for arms in valid_pairs
    )
    regressions = sum(
        arms["baseline"].get("outcome") == "pass" and arms["candidate"].get("outcome") == "fail"
        for arms in valid_pairs
    )
    if reasons:
        verdict = "invalid_protocol"
    elif regressions:
        verdict = "regression"
    elif improvements:
        verdict = "review_candidate"
    else:
        verdict = "no_gain"
    return {
        "verdict": verdict,
        "reasons": sorted(reasons),
        "paired_tasks": len(valid_pairs),
        "expected_tasks": len(evaluation_ids),
        "improvements": improvements,
        "regressions": regressions,
        "evidence_authenticated": False,
        "task_value_proven": False,
        "runtime_or_memory_promotion_authorized": False,
    }


def main() -> int:
    """Read one JSON packet and print its structural audit as JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    args = parser.parse_args()
    try:
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    if not isinstance(packet, dict):
        parser.error("packet root must be a JSON object")
    result = evaluate(packet)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["verdict"] != "invalid_protocol" else 1


if __name__ == "__main__":
    raise SystemExit(main())
