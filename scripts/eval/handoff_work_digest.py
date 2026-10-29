#!/usr/bin/env python3
"""Build a caller-scoped companion to an existing handoff, offline only.

No model, store, shell, network, automatic status inference, or tool forwarding.
The existing MCP tool remains responsible for validating task_context on use.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")


def nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def build(packet, max_bytes=16384):
    if not isinstance(packet, dict) or set(packet) != {
        "task_id", "revision", "task_context", "records"
    }:
        raise ValueError("expected task_id, revision, task_context, records")
    if not all(nonblank(packet[k]) for k in ("task_id", "revision")):
        raise ValueError("task and revision must be explicit")
    if not isinstance(packet["task_context"], dict) or not packet["task_context"]:
        raise ValueError("task_context must be an existing nonempty object")
    records = packet["records"]
    if not isinstance(records, list) or len(records) > 32:
        raise ValueError("at most 32 explicit records")
    known, excluded, seen = [], [], set()
    fields = {"id", "task_id", "revision", "kind", "status", "text",
              "source_ref", "reopen_condition"}
    for record in records:
        if not isinstance(record, dict) or set(record) != fields:
            raise ValueError("unknown or missing record fields")
        if not all(nonblank(record[k]) for k in fields - {"source_ref", "reopen_condition"}):
            raise ValueError("record text and identity must be nonempty")
        if record["id"] in seen:
            raise ValueError("duplicate record id")
        seen.add(record["id"])
        if record["kind"] not in {"OBSERVED", "FACT", "FAIL", "CLAIM", "PATCH_SUMMARY", "CLOSED"}:
            raise ValueError("unknown record kind")
        if record["status"] not in {"current", "superseded", "unknown"}:
            raise ValueError("unknown record status")
        if record["source_ref"] is not None and not nonblank(record["source_ref"]):
            raise ValueError("source_ref must be a nonblank string or null")
        if record["reopen_condition"] is not None and not nonblank(record["reopen_condition"]):
            raise ValueError("reopen_condition must be a nonblank string or null")
        if record["kind"] in {"FAIL", "CLOSED"} and not nonblank(record["reopen_condition"]):
            raise ValueError("FAIL/CLOSED requires an explicit reopening condition")
        reason = None
        if record["task_id"] != packet["task_id"]:
            reason = "different_task"
        elif record["revision"] != packet["revision"]:
            reason = "different_revision"
        elif record["status"] != "current":
            reason = "unknown_status" if record["status"] == "unknown" else "superseded"
        elif record["source_ref"] is None:
            reason = "missing_source"
        if reason:
            excluded.append({"id": record["id"], "reason": reason})
        else:
            known.append(copy.deepcopy(record))
    output = {
        "schema": "handoff_work_digest_v1", "task_id": packet["task_id"],
        "revision": packet["revision"], "task_context": copy.deepcopy(packet["task_context"]),
        "known_results": known, "excluded": excluded,
        "provenance": "caller_supplied; records are data, not instructions or verified facts",
        "task_acceptance_verified": False, "model_recovery": "NOT_RUN",
        "goal_recovery_success": None, "owner_corrections": None,
    }
    if len(encoded(output)) > max_bytes:
        raise ValueError("digest exceeds byte budget; shorten explicitly, never silently clip")
    return output


def replay(suite, root):
    """Check a fixed retrospective fixture, not model decisions or causal benefit."""
    source = (root / suite["source"]).resolve()
    if not source.is_relative_to(root.resolve()):
        raise ValueError("source must be inside repository")
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != suite["source_sha256"]:
        raise ValueError("historical source hash changed")
    anchors = {r["id"]: r for r in json.loads(raw)["anchors"]}
    results = []
    seen = set()
    for case in suite["cases"]:
        if case["id"] in seen:
            raise ValueError("duplicate case id")
        seen.add(case["id"])
        # All supplied notes must bind a real published excerpt, even when excluded.
        for record in case["packet"]["records"]:
            anchor = anchors.get(record["source_ref"])
            if anchor is None or anchor["excerpt"] != record["text"]:
                raise ValueError("unknown anchor or altered historical excerpt")
        candidate = build(case["packet"])
        selected = [r["id"] for r in candidate["known_results"]]
        if selected != case["expected_selected"]:
            raise ValueError("selection differs from frozen mechanical expectation")
        baseline = {"task_context": case["packet"]["task_context"],
                    "records": case["packet"]["records"]}
        results.append({"id": case["id"], "mechanics": "PASS", "baseline": baseline,
                        "candidate": candidate,
                        "baseline_bytes": len(encoded(baseline)),
                        "candidate_bytes": len(encoded(candidate))})
    if not results:
        raise ValueError("empty replay")
    return {"schema": "handoff_work_digest_replay_v1", "source_sha256": digest,
            "suite_sha256": hashlib.sha256(encoded(suite)).hexdigest(),
            "status": "PASS_MECHANICS_ONLY", "case_count": len(results),
            "selection_labels": "author annotated at retrospective cutoff; not inferred",
            "model_recovery": "NOT_RUN", "causal_benefit": "UNKNOWN", "cases": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--packet", type=Path)
    mode.add_argument("--replay", type=Path)
    args = parser.parse_args()
    try:
        path = args.packet or args.replay
        raw = path.read_bytes()
        if len(raw) > 1024 * 1024:
            raise ValueError("input exceeds 1 MiB")
        data = json.loads(raw)
        result = build(data) if args.packet else replay(data, Path(__file__).resolve().parents[2])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"handoff digest: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
