from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "scripts" / "story_voice_cpu_int4_cache_feedback_probe.py"
)
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_cpu_int4_cache_feedback_probe.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_cpu_int4_cache_feedback_probe", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_snapshot(root: Path) -> Path:
    model = root / "cpu_int4" / "talker_cache.onnx"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"fixture")
    return model


def step_summary(past_length: int, present_length: int) -> dict:
    return {
        "past_length": past_length,
        "logits": {
            "shape": [1, 1, 3072],
            "dtype": "float32",
            "all_finite": True,
            "nonzero": True,
        },
        "hidden": {
            "shape": [1, 1, 2048],
            "dtype": "float32",
            "all_finite": True,
        },
        "present_cache": {
            "count": 56,
            "all_shapes": [[1, 8, present_length, 128]],
            "all_finite": True,
        },
    }


def successful_probe() -> dict:
    return {
        "status": "cache_feedback_probe_passed",
        "sequence_contract": {
            "sequence_count": 2,
            "steps_per_sequence": 2,
            "first_position": 0,
            "second_position": 1,
            "second_attention_length": 2,
            "first_embedding_fixture": "bounded_linear_-0.01_0.01",
            "second_embedding_fixture": "bounded_linear_0.01_-0.01",
        },
        "first_step": step_summary(0, 1),
        "second_step": step_summary(1, 2),
        "sha256_sequence_1": "d" * 64,
        "sha256_sequence_2": "d" * 64,
        "deterministic": True,
    }


def test_owner_authorization_blocks_cache_feedback(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    calls = []

    receipt = probe.run_cache_feedback_gate(
        snapshot,
        owner_authorized=False,
        runner=lambda path, timeout: calls.append((path, timeout)),
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["owner_authorization_required"]
    assert calls == []
    assert receipt["runtime_effects"]["fed_back_kv_cache"] is False


def test_exactly_one_cache_feedback_step_passes(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    model = make_snapshot(snapshot)
    calls = []

    receipt = probe.run_cache_feedback_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda path, timeout: (
            calls.append((path, timeout)) or successful_probe()
        ),
        timeout_seconds=31,
    )

    assert calls == [(model, 31)]
    assert receipt["status"] == "talker_cache_feedback_passed_no_sampling"
    assert receipt["blockers"] == []
    assert receipt["runtime_effects"] == {
        "created_inference_session": True,
        "executed_graphs": True,
        "execution_count": 4,
        "produced_kv_cache": True,
        "fed_back_kv_cache": True,
        "cache_feedback_count_per_sequence": 1,
        "sampled_codec_ids": False,
        "generated_tokens": False,
        "rendered_audio": False,
        "played_audio": False,
        "used_gpu": False,
        "imported_community_python": False,
    }


def test_wrong_cache_growth_fails_closed(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    result = successful_probe()
    result["second_step"]["present_cache"]["all_shapes"] = [[1, 8, 1, 128]]

    receipt = probe.run_cache_feedback_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda _path, _timeout: result,
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["second_cache_growth_mismatch"]


def test_nonfinite_or_degenerate_second_step_fails_closed(
    tmp_path: Path,
) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    result = successful_probe()
    result["second_step"]["hidden"]["all_finite"] = False
    result["second_step"]["logits"]["nonzero"] = False

    receipt = probe.run_cache_feedback_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda _path, _timeout: result,
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == [
        "nonfinite_second_step_output",
        "degenerate_second_step_logits",
    ]


def test_nondeterministic_sequence_fails_closed(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    result = successful_probe()
    result["deterministic"] = False

    receipt = probe.run_cache_feedback_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda _path, _timeout: result,
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["nondeterministic_sequence"]


def test_child_failure_does_not_claim_feedback(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)

    receipt = probe.run_cache_feedback_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda _path, _timeout: {
            "status": "cache_feedback_probe_failed",
            "error_type": "InvalidArgument",
            "error": "past cache rejected",
        },
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["cache_feedback_probe_failed"]
    assert receipt["runtime_effects"]["fed_back_kv_cache"] is False


def test_cache_feedback_receipt_validates_against_schema(
    tmp_path: Path,
) -> None:
    jsonschema = __import__("jsonschema")
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    receipt = probe.run_cache_feedback_gate(
        snapshot,
        owner_authorized=False,
        runner=lambda _path, _timeout: successful_probe(),
    )

    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(receipt, schema)
