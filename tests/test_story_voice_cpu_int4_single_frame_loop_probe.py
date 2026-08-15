from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "scripts" / "story_voice_cpu_int4_single_frame_loop_probe.py"
)
SCHEMA_PATH = (
    ROOT
    / "docs"
    / "design"
    / "voice-scene"
    / "voice_cpu_int4_single_frame_loop_probe.schema.json"
)
MODELS = (
    "talker_cache.onnx",
    "code_predictor.onnx",
    "residual_embed.onnx",
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "story_voice_cpu_int4_single_frame_loop_probe", MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_snapshot(root: Path) -> Path:
    model_dir = root / "cpu_int4"
    model_dir.mkdir(parents=True)
    for name in MODELS:
        (model_dir / name).write_bytes(b"fixture")
    return model_dir


def successful_probe() -> dict:
    return {
        "status": "single_frame_loop_probe_passed",
        "selection_contract": {
            "policy": "raw_argmax_exported_logits_no_suppression",
            "local_model_config_present": False,
            "codec_eos_known": False,
            "reserved_token_suppression_applied": False,
            "reference_generation_equivalence_claimed": False,
        },
        "codec_frame": {
            "shape": [1, 16],
            "dtype": "int64",
            "ids": [
                780,
                1224,
                1618,
                1182,
                614,
                904,
                22,
                244,
                14,
                415,
                6,
                529,
                322,
                299,
                1065,
                23,
            ],
            "first_group_vocab": 3072,
            "residual_group_vocab": 2048,
        },
        "step_embedding": {
            "shape": [1, 2048],
            "dtype": "float32",
            "all_finite": True,
            "nonzero": True,
        },
        "second_talker_step": {
            "logits": {
                "shape": [1, 1, 3072],
                "dtype": "float32",
                "all_finite": True,
                "nonzero": True,
            },
            "present_cache": {
                "count": 56,
                "all_shapes": [[1, 8, 2, 128]],
                "all_finite": True,
            },
        },
        "sha256_sequence_1": "f" * 64,
        "sha256_sequence_2": "f" * 64,
        "deterministic": True,
    }


def test_owner_authorization_blocks_all_graphs(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    calls = []

    receipt = probe.run_single_frame_loop_gate(
        snapshot,
        owner_authorized=False,
        runner=lambda paths, timeout: calls.append((paths, timeout)),
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["owner_authorization_required"]
    assert calls == []


def test_one_raw_greedy_codec_frame_loop_passes(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    model_dir = make_snapshot(snapshot)
    calls = []

    receipt = probe.run_single_frame_loop_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda paths, timeout: (
            calls.append((paths, timeout)) or successful_probe()
        ),
        timeout_seconds=41,
    )

    assert calls == [
        ({name: model_dir / name for name in MODELS}, 41)
    ]
    assert receipt["status"] == "single_codec_frame_loop_passed_no_audio"
    assert receipt["blockers"] == []
    assert receipt["runtime_effects"] == {
        "created_inference_sessions": 3,
        "execution_count": 36,
        "talker_execution_count": 4,
        "predictor_execution_count": 30,
        "residual_embed_execution_count": 2,
        "selected_codec_ids": True,
        "sampled_codec_ids": False,
        "generated_codec_frame_count": 1,
        "cache_feedback_count_per_sequence": 1,
        "decoded_waveform": False,
        "rendered_audio": False,
        "played_audio": False,
        "used_gpu": False,
        "imported_community_python": False,
    }


def test_selection_policy_mismatch_fails_closed(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    result = successful_probe()
    result["selection_contract"]["reference_generation_equivalence_claimed"] = True

    receipt = probe.run_single_frame_loop_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda _paths, _timeout: result,
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["selection_contract_mismatch"]


def test_out_of_range_codec_id_fails_closed(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    result = successful_probe()
    result["codec_frame"]["ids"][7] = 2048

    receipt = probe.run_single_frame_loop_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda _paths, _timeout: result,
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["codec_frame_contract_mismatch"]


def test_embedding_or_second_cache_failure_is_blocked(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    result = successful_probe()
    result["step_embedding"]["nonzero"] = False
    result["second_talker_step"]["present_cache"]["all_shapes"] = [
        [1, 8, 1, 128]
    ]

    receipt = probe.run_single_frame_loop_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda _paths, _timeout: result,
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == [
        "step_embedding_contract_mismatch",
        "second_cache_growth_mismatch",
    ]


def test_nondeterministic_loop_fails_closed(tmp_path: Path) -> None:
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    result = successful_probe()
    result["deterministic"] = False

    receipt = probe.run_single_frame_loop_gate(
        snapshot,
        owner_authorized=True,
        runner=lambda _paths, _timeout: result,
    )

    assert receipt["status"] == "blocked"
    assert receipt["blockers"] == ["nondeterministic_sequence"]


def test_receipt_validates_against_schema(tmp_path: Path) -> None:
    jsonschema = __import__("jsonschema")
    probe = load_module()
    snapshot = tmp_path / "snapshot"
    make_snapshot(snapshot)
    receipt = probe.run_single_frame_loop_gate(
        snapshot,
        owner_authorized=False,
        runner=lambda _paths, _timeout: successful_probe(),
    )

    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(receipt, schema)
