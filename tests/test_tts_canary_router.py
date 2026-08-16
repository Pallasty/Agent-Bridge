#!/usr/bin/env python3

import importlib.util
import json
import tempfile
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("router", ROOT / "scripts/tts_canary_router.py")
ROUTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROUTER)
POLICY = json.loads((ROOT / "config/omnivoice-canary.json").read_text())


def call(policy=None, **changes):
    values = {"root": ROOT, "runtime_enabled": True, "subject": "owner-local-pilot",
              "request_id": "request-1", "language": "Chinese", "speaker": "auto",
              "instruction": None, "reference_clone": False}
    values.update(changes)
    return ROUTER.decide(policy or POLICY, **values)


def enabled_policy(percent=100):
    value = deepcopy(POLICY); value["enabled"] = True; value["canary_percent"] = percent
    return value


def test_checked_in_policy_still_requires_runtime_switch():
    result = call(runtime_enabled=False)
    assert result["selected_backend"] == "qwen3"
    assert "runtime_switch_disabled" in result["reasons"]


def test_double_latch_and_allowlist_can_select_candidate():
    result = call(enabled_policy())
    assert result["selected_backend"] == "omnivoice"
    assert result["production_default_change_allowed"] is False


def test_named_voice_and_instruction_stay_on_qwen():
    result = call(enabled_policy(), speaker="Serena", instruction="可爱、轻快")
    assert result["selected_backend"] == "qwen3"
    assert "named_speaker_requires_control" in result["reasons"]
    assert "instruction_requires_control" in result["reasons"]


def test_non_allowlisted_and_clone_stay_on_control():
    result = call(enabled_policy(), subject="other", reference_clone=True)
    assert result["selected_backend"] == "qwen3"
    assert "subject_not_allowlisted" in result["reasons"]
    assert "reference_clone_excluded_from_canary" in result["reasons"]


def test_review_decision_schema_is_fail_closed_even_when_hash_matches():
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        decision = root / "decision.json"
        decision.write_text(json.dumps({"canary_eligible": True}))
        policy = enabled_policy()
        policy["review_decision"] = "decision.json"
        policy["review_decision_sha256"] = ROUTER.sha256(decision)
        result = call(policy, root=root)
    assert result["selected_backend"] == "qwen3"
    assert "review_decision_not_canary_eligible" in result["reasons"]


def test_bucket_is_stable():
    first = call(enabled_policy(10)); second = call(enabled_policy(10))
    assert first["bucket"] == second["bucket"]
    assert first["selected_backend"] == second["selected_backend"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests: test(); print("ok  ", test.__name__)
    print(f"{len(tests)}/{len(tests)} passed")
