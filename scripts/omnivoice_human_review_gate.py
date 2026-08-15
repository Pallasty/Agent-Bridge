#!/usr/bin/env python3
"""Validate a real OmniVoice listening submission before canary admission."""

import argparse
import json
from datetime import datetime
from pathlib import Path


def _score(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a score object")
    required = {"intelligibility", "naturalness", "pronunciation", "artifacts", "overall"}
    if set(value) != required:
        raise ValueError(f"{label} score fields mismatch")
    if any(isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 5 for v in value.values()):
        raise ValueError(f"{label} scores must be integers from 1 through 5")
    return value


def evaluate(policy, submission, root, allow_synthetic=False):
    blockers = []
    if submission.get("schema") != "agent_bridge.omnivoice_human_review_submission.v0":
        raise ValueError("submission schema mismatch")
    synthetic = submission.get("synthetic")
    if not isinstance(synthetic, bool):
        raise ValueError("synthetic must be boolean")
    if synthetic and not allow_synthetic:
        blockers.append("synthetic_submission_not_admissible")
    for field in ("reviewer", "reviewed_at", "playback_device"):
        if not isinstance(submission.get(field), str) or not submission[field].strip():
            blockers.append(f"{field}_missing")
    try:
        datetime.fromisoformat(submission.get("reviewed_at", "").replace("Z", "+00:00"))
    except ValueError:
        blockers.append("reviewed_at_not_iso8601")

    comparisons = []
    expected_packets = {p["id"] for p in policy["packets"]}
    if set(submission.get("scores", {})) != expected_packets:
        raise ValueError("score packet set mismatch")
    for packet in policy["packets"]:
        rows = submission["scores"][packet["id"]]
        if set(rows) != set(packet["samples"]):
            raise ValueError(f"{packet['id']} sample set mismatch")
        key = json.loads((root / packet["answer_key"]).read_text())
        assignments = key.get("assignments", key)
        grouped = {}
        for sample in packet["samples"]:
            scores = _score(rows[sample], f"{packet['id']}.{sample}")
            identity = assignments.get(sample) or assignments.get(sample + ".wav")
            if not identity:
                raise ValueError(f"answer key missing {sample}")
            system = "omnivoice" if "OmniVoice" in identity else "qwen"
            case = sample.rsplit("_", 1)[0]
            grouped.setdefault(case, {})[system] = scores
        for case, systems in grouped.items():
            if set(systems) != {"omnivoice", "qwen"}:
                raise ValueError(f"{packet['id']}.{case} lacks paired systems")
            candidate, qwen = systems["omnivoice"], systems["qwen"]
            for metric, minimum in policy["candidate_minimums"].items():
                if candidate[metric] < minimum:
                    blockers.append(f"{packet['id']}.{case}.{metric}_below_minimum")
                if candidate[metric] < qwen[metric] - policy["maximum_candidate_drop_vs_qwen"]:
                    blockers.append(f"{packet['id']}.{case}.{metric}_regressed_vs_qwen")
            comparisons.append({"packet": packet["id"], "case": case,
                                "candidate": candidate, "qwen": qwen})

    clone = submission.get("clone_review", {})
    for field, minimum in (("speaker_identity_similarity", policy["clone_identity_minimum"]),
                           ("naturalness", policy["clone_naturalness_minimum"])):
        value = clone.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 5:
            blockers.append(f"clone_{field}_invalid")
        elif value < minimum:
            blockers.append(f"clone_{field}_below_minimum")
    if clone.get("confidence") not in {"low", "medium", "high"}:
        blockers.append("clone_confidence_invalid")
    long_ok = submission.get("long_chinese_review", {}).get("key_phrase_pronounced_correctly")
    if policy["long_chinese_key_phrase_required"] and long_ok is not True:
        blockers.append("long_chinese_key_phrase_not_approved")

    admissible = not blockers and not synthetic
    return {
        "schema": "agent_bridge.omnivoice_human_review_gate.v0",
        "status": "canary_eligible" if admissible else "hold",
        "canary_eligible": admissible,
        "production_default_change_allowed": False,
        "synthetic": synthetic,
        "reviewer": submission.get("reviewer"),
        "reviewed_at": submission.get("reviewed_at"),
        "blockers": blockers,
        "comparisons": comparisons,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", type=Path, required=True)
    ap.add_argument("--submission", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--allow-synthetic", action="store_true", help="test evaluation only; never grants canary eligibility")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        result = evaluate(json.loads(args.policy.read_text()),
                          json.loads(args.submission.read_text()),
                          root, args.allow_synthetic)
    except (OSError, json.JSONDecodeError, ValueError, KeyError) as exc:
        result = {
            "schema": "agent_bridge.omnivoice_human_review_gate.v0",
            "status": "validation_error",
            "canary_eligible": False,
            "production_default_change_allowed": False,
            "blockers": [str(exc)],
        }
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    else:
        print(rendered, end="")
    return 0 if result["canary_eligible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
