#!/usr/bin/env python3

import importlib.util
import json
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "omnivoice_human_review_gate", ROOT / "scripts/omnivoice_human_review_gate.py"
)
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)
POLICY = json.loads((ROOT / "config/omnivoice-human-review-policy.json").read_text())


def submission(synthetic=False):
    score = {"intelligibility": 4, "naturalness": 4, "pronunciation": 4,
             "artifacts": 4, "overall": 4}
    return {
        "schema": "agent_bridge.omnivoice_human_review_submission.v0",
        "synthetic": synthetic,
        "reviewer": "synthetic-test-reviewer",
        "reviewed_at": "2026-08-15T12:00:00-07:00",
        "playback_device": "synthetic-test-device",
        "scores": {
            packet["id"]: {sample: deepcopy(score) for sample in packet["samples"]}
            for packet in POLICY["packets"]
        },
        "clone_review": {"speaker_identity_similarity": 4, "naturalness": 4,
                         "confidence": "high", "notes": "synthetic"},
        "long_chinese_review": {"key_phrase_pronounced_correctly": True,
                                "notes": "synthetic"},
        "notes": "synthetic test object only",
    }


def test_complete_real_shaped_submission_can_reach_canary_only():
    result = GATE.evaluate(POLICY, submission(False), ROOT)
    assert result["canary_eligible"] is True
    assert result["production_default_change_allowed"] is False


def test_synthetic_submission_never_unlocks_canary():
    result = GATE.evaluate(POLICY, submission(True), ROOT, allow_synthetic=True)
    assert result["canary_eligible"] is False
    assert result["status"] == "hold"


def test_low_candidate_score_blocks():
    value = submission(False)
    value["scores"]["basic"]["english_A"]["pronunciation"] = 3
    result = GATE.evaluate(POLICY, value, ROOT)
    assert result["canary_eligible"] is False
    assert "basic.english.pronunciation_below_minimum" in result["blockers"]


def test_clone_and_long_chinese_are_required():
    value = submission(False)
    value["clone_review"]["speaker_identity_similarity"] = 3
    value["long_chinese_review"]["key_phrase_pronounced_correctly"] = False
    result = GATE.evaluate(POLICY, value, ROOT)
    assert "clone_speaker_identity_similarity_below_minimum" in result["blockers"]
    assert "long_chinese_key_phrase_not_approved" in result["blockers"]


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items())
             if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"ok   {test.__name__}")
    print(f"{len(tests)}/{len(tests)} passed")
