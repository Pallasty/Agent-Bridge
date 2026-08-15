from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "story_voice_cpu_int4_talker_cache_probe.py"
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_cpu_int4_talker_cache_probe.schema.json"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_cpu_int4_talker_cache_probe", MODULE_PATH
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


def successful_probe() -> dict:
    return {
        "status": "talker_cache_probe_passed",
        "input_contract": {
            "input_count": 59,
            "current_length": 1,
            "past_length": 0,
            "kv_input_count": 56,
            "embedding_fixture": "bounded_linear_-0.01_0.01",
        },
        "logits": {
            "shape": [1, 1, 3072],
            "dtype": "float32",
            "all_finite": True,
            "minimum": -1.0,
            "maximum": 1.0,
            "mean": 0.0,
            "nonzero": True,
        },
        "hidden": {
            "shape": [1, 1, 2048],
            "dtype": "float32",
            "all_finite": True,
        },
        "present_cache": {
            "count": 56,
            "all_shapes": [[1, 8, 1, 128]],
            "all_finite": True,
        },
        "sha256_run_1": "c" * 64,
        "sha256_run_2": "c" * 64,
        "deterministic": True,
    }


def test_owner_authorization_blocks_talker_execution(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    calls = []

    receipt = probe.run_talker_gate(
        snapshot,
        owner_authorized=False,
        runner=lambda path, timeout: calls.append((path, timeout)),
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["owner_authorization_required"]
    assert calls == []


def test_zero_cache_single_step_passes_with_finite_deterministic_outputs(
    tmp_path: Path,
) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    model = make_snapshot(snapshot)
    calls = []

    receipt = probe.run_talker_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda path, timeout: (
            calls.append((path, timeout)) or successful_probe()
        ),
        timeout_seconds=29,
    )

    assert calls == [(model, 29)]
    assert receipt["status"] == "talker_single_step_passed_no_sampling"
    assert receipt["blockers"] == []
    assert receipt["runtime_effects"] == {
        "created_inference_session": True,
        "executed_graphs": True,
        "execution_count": 2,
        "produced_kv_cache": True,
        "fed_back_kv_cache": False,
        "sampled_codec_ids": False,
        "generated_tokens": False,
        "rendered_audio": False,
        "played_audio": False,
        "used_gpu": False,
        "imported_community_python": False,
    }


def test_invalid_cache_or_nondeterminism_fails_closed(
    tmp_path: Path,
) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    result = successful_probe()
    result["present_cache"]["all_shapes"] = [[1, 8, 2, 128]]
    result["deterministic"] = False

    receipt = probe.run_talker_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda _path, _timeout: result,
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == [
        "present_cache_contract_mismatch",
        "nondeterministic_output",
    ]


def test_degenerate_zero_logits_fail_closed(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    result = successful_probe()
    result["logits"]["nonzero"] = False

    receipt = probe.run_talker_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda _path, _timeout: result,
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["degenerate_zero_logits"]


def test_child_failure_is_recorded_without_cache_feedback(
    tmp_path: Path,
) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)

    receipt = probe.run_talker_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda _path, _timeout: {
            "status": "talker_cache_probe_failed",
            "error_type": "InvalidArgument",
            "error": "cache contract mismatch",
        },
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["talker_cache_probe_failed"]
    assert receipt["runtime_effects"]["fed_back_kv_cache"] is False


def test_talker_receipt_validates_against_schema(tmp_path: Path) -> None:
    jsonschema = __import__("jsonschema")
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    receipt = probe.run_talker_gate(
        snapshot,
        owner_authorized=False,
        runner=lambda _path, _timeout: successful_probe(),
    )

    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(receipt, schema)
