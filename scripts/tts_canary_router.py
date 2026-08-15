#!/usr/bin/env python3
"""Pure, review-bound, allowlisted TTS canary routing decision."""

import argparse
import hashlib
import json
import os
from pathlib import Path


ALIASES = {"zh": "chinese", "en": "english"}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decide(policy, *, root, runtime_enabled, subject, request_id, language,
           speaker=None, instruction=None, reference_clone=False):
    root = Path(root)
    reasons = []
    language = ALIASES.get(language.lower(), language.lower())
    review_path = root / policy["review_decision"]
    review = None
    if not review_path.is_file() or sha256(review_path) != policy["review_decision_sha256"]:
        reasons.append("review_decision_binding_failed")
    else:
        try:
            review = json.loads(review_path.read_text())
        except (OSError, json.JSONDecodeError):
            reasons.append("review_decision_invalid")
        if review is not None and (
                review.get("schema") != "agent_bridge.omnivoice_human_review_gate.v0" or
                review.get("status") != "canary_eligible" or
                review.get("canary_eligible") is not True or
                review.get("production_default_change_allowed") is not False or
                review.get("synthetic") is not False or
                review.get("blockers") != []):
            reasons.append("review_decision_not_canary_eligible")
    if not runtime_enabled:
        reasons.append("runtime_switch_disabled")
    if policy.get("enabled") is not True:
        reasons.append("policy_disabled")
    if subject not in policy.get("allowlisted_subjects", []):
        reasons.append("subject_not_allowlisted")
    if not request_id:
        reasons.append("request_id_missing")
    if language not in policy["eligible_languages"]:
        reasons.append("language_not_canary_eligible")
    if speaker and speaker.lower() not in {"auto", "default", "omnivoice"}:
        reasons.append("named_speaker_requires_control")
    if instruction:
        reasons.append("instruction_requires_control")
    if reference_clone:
        reasons.append("reference_clone_excluded_from_canary")
    percent = policy.get("canary_percent")
    if isinstance(percent, bool) or not isinstance(percent, int) or not 0 <= percent <= 100:
        raise ValueError("canary_percent must be an integer from 0 through 100")
    bucket = None
    if request_id:
        digest = hashlib.sha256(f"{policy['salt']}\0{subject}\0{request_id}".encode()).digest()
        bucket = int.from_bytes(digest[:4], "big") % 10000
        if bucket >= percent * 100:
            reasons.append("outside_percentage_bucket")
    selected = policy["candidate_backend"] if not reasons else policy["control_backend"]
    return {
        "schema": "agent_bridge.tts_canary_decision.v0",
        "selected_backend": selected,
        "candidate_selected": not reasons,
        "subject": subject,
        "request_id": request_id,
        "language": language,
        "bucket": bucket,
        "canary_percent": percent,
        "reasons": reasons,
        "production_default_change_allowed": False,
        "review_decision_sha256": policy["review_decision_sha256"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", type=Path, required=True)
    ap.add_argument("--subject", required=True)
    ap.add_argument("--request-id", required=True)
    ap.add_argument("--language", required=True)
    ap.add_argument("--speaker")
    ap.add_argument("--instruction")
    ap.add_argument("--reference-clone", action="store_true")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    enabled = os.environ.get("AB_TTS_CANARY_ENABLED", "").strip().lower() in {
        "1", "true", "yes", "on"
    }
    result = decide(json.loads(args.policy.read_text()), root=root,
                    runtime_enabled=enabled, subject=args.subject,
                    request_id=args.request_id, language=args.language,
                    speaker=args.speaker, instruction=args.instruction,
                    reference_clone=args.reference_clone)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
