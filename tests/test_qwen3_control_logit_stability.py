import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/eval/qwen3_control_logit_stability.py"
POLICY = ROOT / "scripts/eval/fixtures/qwen3_tts_control_logit_stability_policy_v0.json"
BURNIN_SCRIPT = ROOT / "scripts/eval/qwen3_control_logit_stability_burnin.py"
BURNIN_POLICY = ROOT / "scripts/eval/fixtures/qwen3_tts_control_logit_stability_policy_v1.json"


def load_module():
    spec = importlib.util.spec_from_file_location("qwen3_control_logit_stability", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def logits(*, dtype=np.float16):
    return np.asarray([[0, 1, 2, 3, 4, 5, 6, 7, 8], [8, 7, 6, 5, 4, 3, 2, 1, 0]], dtype=dtype)


def test_identical_logits_are_bit_exact():
    module = load_module()
    value = logits()
    metrics = module.compare_logit_arrays(value, value.copy())
    assert metrics["exact"] is True
    assert metrics["max_ulp_delta"] == 0
    assert metrics["changed_rows"] == []
    assert module.classify_path([metrics]) == "BIT_EXACT"


def test_small_rank_preserving_delta_is_numerically_stable():
    module = load_module()
    left = logits()
    right = left.copy()
    right[:, 0] = np.nextafter(right[:, 0], np.float16(1), dtype=np.float16)
    metrics = module.compare_logit_arrays(left, right)
    assert metrics["exact"] is False
    assert metrics["top1_agreement"] == 1.0
    assert metrics["top8_retention"] == 1.0
    assert metrics["changed_rows"] == [0, 1]
    assert module.classify_path([metrics]) == "NUMERICALLY_STABLE_WITHIN_CONTROL_ENVELOPE"


def test_top_rank_or_shape_drift_is_unstable():
    module = load_module()
    left = logits()
    right = left.copy()
    right[0, 0] = np.float16(10)
    assert module.classify_path([module.compare_logit_arrays(left, right)]) == "UNSTABLE"
    assert module.classify_path([module.compare_logit_arrays(left, right[:, :-1])]) == "UNSTABLE"


def test_nonfinite_logits_are_unstable():
    module = load_module()
    left = logits()
    right = left.copy()
    right[0, 0] = np.nan
    metrics = module.compare_logit_arrays(left, right)
    assert metrics["finite"] is False
    assert module.classify_path([metrics]) == "UNSTABLE"


def test_six_trials_produce_all_fifteen_pairs():
    module = load_module()
    trials = [{"value": logits()} for _ in module.TRIAL_LABELS]
    summary = module.summarize_path(trials, lambda trial: trial["value"])
    assert summary["pair_count"] == 15
    assert summary["exact_pair_count"] == 15
    assert summary["classification"] == "BIT_EXACT"
    assert summary["warm_only_classification"] == "BIT_EXACT"
    assert summary["retains_full_logits"] is False


def test_policy_is_control_only_and_rejects_authority_drift():
    module = load_module()
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    module.validate_policy(policy)
    policy["authority"]["allows_fake_q8"] = True
    with pytest.raises(ValueError, match="grants authority"):
        module.validate_policy(policy)


def test_runner_contains_no_audio_or_quantized_weight_writer():
    source = SCRIPT.read_text(encoding="utf-8")
    forbidden = ("soundfile", "save_pretrained", "save_file(", "temporary_linear_forward_proxy", "worker.sock")
    assert all(token not in source for token in forbidden)


def test_burnin_policy_has_two_unmeasured_calls_and_six_measurements():
    module = load_module()
    policy = json.loads(BURNIN_POLICY.read_text(encoding="utf-8"))
    burnin = importlib.util.spec_from_file_location("qwen3_control_logit_stability_burnin", BURNIN_SCRIPT)
    burnin_module = importlib.util.module_from_spec(burnin)
    assert burnin.loader is not None
    burnin.loader.exec_module(burnin_module)
    burnin_module.validate_policy(policy)
    assert policy["burn_in_labels"] == ["B0_burn_in", "B1_burn_in"]
    assert len(policy["trial_labels"]) == 6
    trials = [{"value": logits()} for _ in policy["trial_labels"]]
    assert module.summarize_path(trials, lambda trial: trial["value"], policy["trial_labels"])["pair_count"] == 15
